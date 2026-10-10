from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator, MinValueValidator
from django.db import models
from django.db.models import Q


class CompanySettings(models.Model):
    company_name = models.CharField(max_length=200, default="Zuuvi")
    currency = models.CharField(max_length=8, default="INR")
    financial_year_start_month = models.PositiveSmallIntegerField(
        default=4,
        help_text="Calendar month when the financial year starts (1–12). Default is April.",
    )
    budget_warning_threshold = models.PositiveSmallIntegerField(
        default=90,
        help_text="Utilization percentage at which a category is marked Near Limit.",
    )

    class Meta:
        verbose_name = "Company settings"
        verbose_name_plural = "Company settings"

    def __str__(self):
        return self.company_name

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass

    @classmethod
    def get_solo(cls):
        obj, _created = cls.objects.get_or_create(pk=1)
        return obj

    def clean(self):
        if not 1 <= self.financial_year_start_month <= 12:
            raise ValidationError({"financial_year_start_month": "Must be between 1 and 12."})
        if not 1 <= self.budget_warning_threshold <= 100:
            raise ValidationError({"budget_warning_threshold": "Must be between 1 and 100."})


class Category(models.Model):
    INCOME = "income"
    EXPENSE = "expense"
    TYPE_CHOICES = [
        (INCOME, "Income"),
        (EXPENSE, "Expense"),
    ]

    name = models.CharField(max_length=100)
    category_type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["category_type", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["name", "category_type"],
                name="unique_category_name_type",
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.get_category_type_display()})"

    def has_transactions(self):
        return self.transactions.exists()


class Account(models.Model):
    BANK = "bank"
    CASH = "cash"
    PETTY_CASH = "petty_cash"
    UPI = "upi"
    TYPE_CHOICES = [
        (BANK, "Bank"),
        (CASH, "Cash"),
        (PETTY_CASH, "Petty Cash"),
        (UPI, "UPI"),
    ]

    name = models.CharField(max_length=100, unique=True)
    account_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    bank_name = models.CharField(max_length=100, blank=True)
    account_number = models.CharField(
        max_length=32,
        blank=True,
        help_text="Full number or last four digits. Do not store PINs, passwords, or OTPs.",
    )
    opening_balance = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    opening_balance_date = models.DateField(
        help_text=(
            "Transactions dated before this date are excluded from the current balance "
            "because they are assumed to already be reflected in the opening balance."
        )
    )
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def clean(self):
        if self.account_type in {self.CASH, self.PETTY_CASH}:
            return
        # Bank/UPI may omit bank_name; no extra required fields.

    def has_transactions(self):
        return self.transactions.exists()


class Transaction(models.Model):
    DEBIT = "debit"
    CREDIT = "credit"
    ENTRY_CHOICES = [
        (DEBIT, "Debit (money out)"),
        (CREDIT, "Credit (money in)"),
    ]

    KIND_OPERATING = "operating"
    KIND_TRANSFER = "transfer"
    KIND_CHOICES = [
        (KIND_OPERATING, "Operating"),
        (KIND_TRANSFER, "Internal transfer"),
    ]

    date = models.DateField()
    entry_type = models.CharField(max_length=10, choices=ENTRY_CHOICES)
    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="transactions",
        null=True,
        blank=True,
    )
    account = models.ForeignKey(
        Account,
        on_delete=models.PROTECT,
        related_name="transactions",
    )
    description = models.CharField(max_length=255)
    reference_number = models.CharField(max_length=80, blank=True)
    notes = models.TextField(blank=True)
    receipt = models.FileField(
        upload_to="receipts/%Y/%m/",
        blank=True,
        validators=[FileExtensionValidator(["pdf", "png", "jpg", "jpeg", "webp"])],
    )
    kind = models.CharField(max_length=12, choices=KIND_CHOICES, default=KIND_OPERATING)
    transfer_group = models.UUIDField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "-id"]
        constraints = [
            models.CheckConstraint(condition=Q(amount__gt=0), name="txn_amount_positive"),
            models.CheckConstraint(
                condition=(
                    Q(kind="operating", category__isnull=False)
                    | Q(kind="transfer", category__isnull=True)
                ),
                name="txn_category_matches_kind",
            ),
        ]

    def __str__(self):
        return f"{self.date} {self.entry_type} {self.amount} {self.description}"

    def clean(self):
        if self.amount is not None and self.amount <= 0:
            raise ValidationError({"amount": "Amount must be greater than zero."})

        if self.kind == self.KIND_TRANSFER:
            if self.category_id:
                raise ValidationError(
                    {"category": "Internal transfers must not have an income or expense category."}
                )
            return

        if not self.category_id:
            raise ValidationError({"category": "Category is required for income and expense transactions."})

        category = self.category
        if category is None and self.category_id:
            category = Category.objects.filter(pk=self.category_id).first()
        if category is None:
            raise ValidationError({"category": "Select a valid category."})

        if self.entry_type == self.DEBIT and category.category_type != Category.EXPENSE:
            raise ValidationError(
                {"category": "Debit (expense) transactions must use an expense category."}
            )
        if self.entry_type == self.CREDIT and category.category_type != Category.INCOME:
            raise ValidationError(
                {"category": "Credit (income) transactions must use an income category."}
            )


class Budget(models.Model):
    year = models.PositiveIntegerField()
    month = models.PositiveSmallIntegerField()
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="budgets",
        limit_choices_to={"category_type": Category.EXPENSE},
    )
    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["category__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["year", "month", "category"],
                name="unique_budget_year_month_category",
            ),
            models.CheckConstraint(condition=Q(month__gte=1, month__lte=12), name="budget_month_valid"),
            models.CheckConstraint(condition=Q(amount__gt=0), name="budget_amount_positive"),
        ]

    def __str__(self):
        return f"{self.year}-{self.month:02d} {self.category} {self.amount}"

    def clean(self):
        if self.month and not 1 <= self.month <= 12:
            raise ValidationError({"month": "Month must be between 1 and 12."})
        if self.category_id:
            category = self.category
            if category.category_type != Category.EXPENSE:
                raise ValidationError({"category": "Budgets can only be created for expense categories."})
        if self.amount is not None and self.amount <= 0:
            raise ValidationError({"amount": "Budget amount must be greater than zero."})
