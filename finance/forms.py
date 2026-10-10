from decimal import Decimal

from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError

from .models import Account, Budget, Category, CompanySettings, Transaction
from .period import MONTH_CHOICES


class StyledAuthenticationForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update({"class": "form-control", "autofocus": True})
        self.fields["password"].widget.attrs.update({"class": "form-control"})
        self.error_messages["invalid_login"] = (
            "Please enter a valid username and password. Both fields may be case-sensitive."
        )


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name", "category_type", "description", "is_active"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "category_type": forms.Select(attrs={"class": "form-select"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class AccountForm(forms.ModelForm):
    class Meta:
        model = Account
        fields = [
            "name",
            "account_type",
            "bank_name",
            "account_number",
            "opening_balance",
            "opening_balance_date",
            "notes",
            "is_active",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "account_type": forms.Select(attrs={"class": "form-select"}),
            "bank_name": forms.TextInput(attrs={"class": "form-control"}),
            "account_number": forms.TextInput(attrs={"class": "form-control"}),
            "opening_balance": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "opening_balance_date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
        help_texts = {
            "account_number": "Optional. Last four digits are enough. Never store banking passwords, PINs, or OTPs.",
            "opening_balance_date": (
                "Transactions before this date are excluded from the current balance "
                "because they are assumed to already be part of the opening balance."
            ),
        }


class TransactionForm(forms.ModelForm):
    class Meta:
        model = Transaction
        fields = [
            "date",
            "entry_type",
            "amount",
            "category",
            "account",
            "description",
            "reference_number",
            "notes",
            "receipt",
        ]
        widgets = {
            "date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "entry_type": forms.Select(attrs={"class": "form-select"}),
            "amount": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0.01"}),
            "category": forms.Select(attrs={"class": "form-select"}),
            "account": forms.Select(attrs={"class": "form-select"}),
            "description": forms.TextInput(attrs={"class": "form-control"}),
            "reference_number": forms.TextInput(attrs={"class": "form-control"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "receipt": forms.ClearableFileInput(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = Category.objects.filter(is_active=True).order_by(
            "category_type", "name"
        )
        self.fields["account"].queryset = Account.objects.filter(is_active=True)
        if self.instance and self.instance.pk:
            if self.instance.category_id:
                self.fields["category"].queryset |= Category.objects.filter(pk=self.instance.category_id)
            if self.instance.account_id:
                self.fields["account"].queryset |= Account.objects.filter(pk=self.instance.account_id)

    def clean_amount(self):
        amount = self.cleaned_data["amount"]
        if amount is None or amount <= 0:
            raise ValidationError("Amount must be greater than zero.")
        return amount

    def clean_receipt(self):
        receipt = self.cleaned_data.get("receipt")
        if receipt and hasattr(receipt, "size") and receipt.size > 5 * 1024 * 1024:
            raise ValidationError("Receipt files must be 5 MB or smaller.")
        return receipt

    def clean(self):
        cleaned = super().clean()
        entry_type = cleaned.get("entry_type")
        category = cleaned.get("category")
        if category and entry_type == Transaction.DEBIT and category.category_type != Category.EXPENSE:
            self.add_error("category", "Debit transactions must use an expense category.")
        if category and entry_type == Transaction.CREDIT and category.category_type != Category.INCOME:
            self.add_error("category", "Credit transactions must use an income category.")
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.kind = Transaction.KIND_OPERATING
        instance.transfer_group = None
        if commit:
            instance.full_clean()
            instance.save()
        return instance


class TransferForm(forms.Form):
    date = forms.DateField(widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}))
    amount = forms.DecimalField(
        max_digits=14,
        decimal_places=2,
        min_value=Decimal("0.01"),
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0.01"}),
    )
    source_account = forms.ModelChoiceField(
        queryset=Account.objects.none(),
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    destination_account = forms.ModelChoiceField(
        queryset=Account.objects.none(),
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    description = forms.CharField(
        max_length=255,
        initial="Internal transfer",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    reference_number = forms.CharField(
        required=False,
        max_length=80,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        accounts = Account.objects.filter(is_active=True)
        self.fields["source_account"].queryset = accounts
        self.fields["destination_account"].queryset = accounts

    def clean(self):
        cleaned = super().clean()
        source = cleaned.get("source_account")
        dest = cleaned.get("destination_account")
        if source and dest and source.pk == dest.pk:
            raise ValidationError("Source and destination accounts must be different.")
        return cleaned


class BudgetForm(forms.ModelForm):
    month = forms.TypedChoiceField(
        coerce=int,
        choices=MONTH_CHOICES,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    class Meta:
        model = Budget
        fields = ["year", "month", "category", "amount", "notes"]
        widgets = {
            "year": forms.NumberInput(attrs={"class": "form-control", "min": "2000"}),
            "category": forms.Select(attrs={"class": "form-select"}),
            "amount": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0.01"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = Category.objects.filter(
            category_type=Category.EXPENSE, is_active=True
        )
        if self.instance and self.instance.pk and self.instance.category_id:
            self.fields["category"].queryset |= Category.objects.filter(pk=self.instance.category_id)

    def clean(self):
        cleaned = super().clean()
        year = cleaned.get("year")
        month = cleaned.get("month")
        category = cleaned.get("category")
        if year and month and category:
            qs = Budget.objects.filter(year=year, month=month, category=category)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise ValidationError("A budget for this category already exists for the selected month.")
        return cleaned


class SettingsForm(forms.ModelForm):
    class Meta:
        model = CompanySettings
        fields = ["company_name", "currency", "financial_year_start_month", "budget_warning_threshold"]
        widgets = {
            "company_name": forms.TextInput(attrs={"class": "form-control"}),
            "currency": forms.TextInput(attrs={"class": "form-control"}),
            "financial_year_start_month": forms.Select(
                choices=MONTH_CHOICES, attrs={"class": "form-select"}
            ),
            "budget_warning_threshold": forms.NumberInput(
                attrs={"class": "form-control", "min": "1", "max": "100"}
            ),
        }
