from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from .models import Account, Budget, Category, CompanySettings, Transaction
from .services import (
    STATUS_FULL,
    STATUS_NEAR,
    STATUS_OVER,
    STATUS_UNBUDGETED,
    STATUS_WITHIN,
    account_balance,
    budget_vs_actual,
    create_transfer,
    dashboard_summary,
    expenses_by_category,
    income_expense_totals,
)


class FinanceBaseTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="owner", password="test-pass-123")
        self.expense_fuel = Category.objects.create(name="Fuel", category_type=Category.EXPENSE)
        self.expense_salary = Category.objects.create(name="Salaries", category_type=Category.EXPENSE)
        self.expense_rent = Category.objects.create(name="Office Rent", category_type=Category.EXPENSE)
        self.income_sales = Category.objects.create(name="Sales Income", category_type=Category.INCOME)
        self.sbi = Account.objects.create(
            name="SBI Current Account",
            account_type=Account.BANK,
            bank_name="SBI",
            opening_balance=Decimal("100000.00"),
            opening_balance_date=date(2026, 10, 1),
        )
        self.hdfc = Account.objects.create(
            name="HDFC Current Account",
            account_type=Account.BANK,
            bank_name="HDFC",
            opening_balance=Decimal("50000.00"),
            opening_balance_date=date(2026, 10, 1),
        )
        self.cash = Account.objects.create(
            name="Cash",
            account_type=Account.CASH,
            opening_balance=Decimal("0.00"),
            opening_balance_date=date(2026, 10, 1),
        )

    def login(self):
        self.client.login(username="owner", password="test-pass-123")

    def add_txn(self, **kwargs):
        defaults = {
            "date": date(2026, 10, 7),
            "entry_type": Transaction.DEBIT,
            "amount": Decimal("2500.00"),
            "category": self.expense_fuel,
            "account": self.sbi,
            "description": "Delivery vehicle fuel",
            "kind": Transaction.KIND_OPERATING,
        }
        defaults.update(kwargs)
        txn = Transaction(**defaults)
        txn.full_clean()
        txn.save()
        return txn


class AuthTests(FinanceBaseTestCase):
    def test_login_success_and_failure(self):
        response = self.client.post(reverse("login"), {"username": "owner", "password": "wrong"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "valid username and password")

        response = self.client.post(reverse("login"), {"username": "owner", "password": "test-pass-123"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("finance:dashboard"))

    def test_protected_pages_require_login(self):
        for name in [
            "finance:dashboard",
            "finance:transaction_list",
            "finance:budget_list",
            "finance:account_list",
            "finance:category_list",
            "finance:reports",
            "finance:settings",
        ]:
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 302)
            self.assertIn("/login/", response.url)


class BudgetTests(FinanceBaseTestCase):
    def test_create_and_edit_budget(self):
        self.login()
        response = self.client.post(
            reverse("finance:budget_create"),
            {
                "year": 2026,
                "month": 10,
                "category": self.expense_fuel.pk,
                "amount": "25000.00",
                "notes": "October fuel",
            },
        )
        self.assertEqual(response.status_code, 302)
        budget = Budget.objects.get()
        self.assertEqual(budget.amount, Decimal("25000.00"))

        response = self.client.post(
            reverse("finance:budget_edit", args=[budget.pk]),
            {
                "year": 2026,
                "month": 10,
                "category": self.expense_fuel.pk,
                "amount": "27000.00",
                "notes": "Revised",
            },
        )
        self.assertEqual(response.status_code, 302)
        budget.refresh_from_db()
        self.assertEqual(budget.amount, Decimal("27000.00"))

    def test_duplicate_category_month_budget_rejected(self):
        Budget.objects.create(year=2026, month=10, category=self.expense_fuel, amount=Decimal("25000"))
        self.login()
        response = self.client.post(
            reverse("finance:budget_create"),
            {
                "year": 2026,
                "month": 10,
                "category": self.expense_fuel.pk,
                "amount": "1000.00",
                "notes": "",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Budget.objects.count(), 1)
        self.assertContains(response, "already exists")


class TransactionAndBudgetCalcTests(FinanceBaseTestCase):
    def test_debit_and_credit_transactions(self):
        debit = self.add_txn()
        credit = self.add_txn(
            entry_type=Transaction.CREDIT,
            amount=Decimal("15000.00"),
            category=self.income_sales,
            account=self.hdfc,
            description="Customer payment",
        )
        self.assertEqual(debit.entry_type, Transaction.DEBIT)
        self.assertEqual(credit.entry_type, Transaction.CREDIT)
        totals = income_expense_totals(2026, 10)
        self.assertEqual(totals["income"], Decimal("15000.00"))
        self.assertEqual(totals["expenses"], Decimal("2500.00"))
        self.assertEqual(totals["net_cash_flow"], Decimal("12500.00"))

    def test_zero_or_negative_amount_rejected(self):
        txn = Transaction(
            date=date(2026, 10, 7),
            entry_type=Transaction.DEBIT,
            amount=Decimal("0.00"),
            category=self.expense_fuel,
            account=self.sbi,
            description="Invalid",
        )
        with self.assertRaises(ValidationError):
            txn.full_clean()

    def test_budget_remaining_and_statuses(self):
        Budget.objects.create(year=2026, month=10, category=self.expense_salary, amount=Decimal("80000"))
        Budget.objects.create(year=2026, month=10, category=self.expense_fuel, amount=Decimal("25000"))
        Budget.objects.create(year=2026, month=10, category=self.expense_rent, amount=Decimal("20000"))
        marketing = Category.objects.create(name="Marketing", category_type=Category.EXPENSE)
        Budget.objects.create(year=2026, month=10, category=marketing, amount=Decimal("15000"))
        unbudgeted = Category.objects.create(name="Packaging", category_type=Category.EXPENSE)

        self.add_txn(category=self.expense_salary, amount=Decimal("75000"), description="Salary")
        self.add_txn(category=self.expense_fuel, amount=Decimal("27500"), description="Fuel")
        self.add_txn(category=self.expense_rent, amount=Decimal("20000"), description="Rent")
        self.add_txn(category=marketing, amount=Decimal("8000"), description="Ads")
        self.add_txn(category=unbudgeted, amount=Decimal("1200"), description="Boxes")

        CompanySettings.get_solo()
        bva = budget_vs_actual(2026, 10, threshold=90)
        by_name = {row["category"]: row for row in bva["rows"]}
        self.assertEqual(by_name["Salaries"]["status"], STATUS_NEAR)
        self.assertEqual(by_name["Salaries"]["remaining"], Decimal("5000.00"))
        self.assertEqual(by_name["Fuel"]["status"], STATUS_OVER)
        self.assertEqual(by_name["Fuel"]["remaining"], Decimal("-2500.00"))
        self.assertEqual(by_name["Office Rent"]["status"], STATUS_FULL)
        self.assertEqual(by_name["Marketing"]["status"], STATUS_WITHIN)
        self.assertEqual(bva["unbudgeted"][0]["status"], STATUS_UNBUDGETED)
        self.assertEqual(bva["unbudgeted"][0]["actual"], Decimal("1200.00"))

    def test_month_filtering(self):
        self.add_txn(date=date(2026, 10, 5), amount=Decimal("1000"))
        self.add_txn(date=date(2026, 11, 5), amount=Decimal("4000"))
        self.assertEqual(income_expense_totals(2026, 10)["expenses"], Decimal("1000.00"))
        self.assertEqual(income_expense_totals(2026, 11)["expenses"], Decimal("4000.00"))


class AccountAndTransferTests(FinanceBaseTestCase):
    def test_account_balance_formula_and_opening_date(self):
        self.add_txn(amount=Decimal("2500"))
        self.add_txn(
            entry_type=Transaction.CREDIT,
            amount=Decimal("15000"),
            category=self.income_sales,
            description="Sale",
        )
        self.add_txn(
            date=date(2026, 9, 20),
            amount=Decimal("9999"),
            description="Before opening date",
        )
        self.assertEqual(account_balance(self.sbi), Decimal("112500.00"))

    def test_internal_transfer_moves_money_without_affecting_pnl(self):
        Budget.objects.create(year=2026, month=10, category=self.expense_fuel, amount=Decimal("25000"))
        create_transfer(
            date=date(2026, 10, 8),
            amount=Decimal("10000"),
            source=self.sbi,
            destination=self.hdfc,
            description="Move to HDFC",
        )
        self.assertEqual(account_balance(self.sbi), Decimal("90000.00"))
        self.assertEqual(account_balance(self.hdfc), Decimal("60000.00"))
        totals = income_expense_totals(2026, 10)
        self.assertEqual(totals["income"], Decimal("0.00"))
        self.assertEqual(totals["expenses"], Decimal("0.00"))
        bva = budget_vs_actual(2026, 10)
        self.assertEqual(bva["total_actual"], Decimal("0.00"))
        self.assertEqual(Transaction.objects.filter(kind=Transaction.KIND_TRANSFER).count(), 2)

    def test_transfer_same_account_rejected(self):
        with self.assertRaises(ValueError):
            create_transfer(
                date=date(2026, 10, 8),
                amount=Decimal("100"),
                source=self.sbi,
                destination=self.sbi,
                description="Invalid",
            )

    def test_edit_and_delete_transaction_recalculates(self):
        txn = self.add_txn(amount=Decimal("2500"))
        self.assertEqual(account_balance(self.sbi), Decimal("97500.00"))
        txn.amount = Decimal("5000")
        txn.full_clean()
        txn.save()
        self.assertEqual(account_balance(self.sbi), Decimal("95000.00"))
        txn.delete()
        self.assertEqual(account_balance(self.sbi), Decimal("100000.00"))


class CategoryValidationTests(FinanceBaseTestCase):
    def test_income_category_cannot_be_used_for_debit(self):
        txn = Transaction(
            date=date(2026, 10, 7),
            entry_type=Transaction.DEBIT,
            amount=Decimal("100"),
            category=self.income_sales,
            account=self.sbi,
            description="Wrong type",
        )
        with self.assertRaises(ValidationError):
            txn.full_clean()

    def test_expense_category_cannot_be_used_for_credit(self):
        txn = Transaction(
            date=date(2026, 10, 7),
            entry_type=Transaction.CREDIT,
            amount=Decimal("100"),
            category=self.expense_fuel,
            account=self.sbi,
            description="Wrong type",
        )
        with self.assertRaises(ValidationError):
            txn.full_clean()

    def test_referenced_category_is_deactivated_not_deleted(self):
        self.login()
        self.add_txn()
        response = self.client.post(reverse("finance:category_delete", args=[self.expense_fuel.pk]))
        self.assertEqual(response.status_code, 302)
        self.expense_fuel.refresh_from_db()
        self.assertFalse(self.expense_fuel.is_active)
        self.assertTrue(Category.objects.filter(pk=self.expense_fuel.pk).exists())


class ReportConsistencyTests(FinanceBaseTestCase):
    def test_reports_match_underlying_transactions_and_dashboard(self):
        Budget.objects.create(year=2026, month=10, category=self.expense_fuel, amount=Decimal("25000"))
        self.add_txn(amount=Decimal("2500"))
        self.add_txn(
            entry_type=Transaction.CREDIT,
            amount=Decimal("15000"),
            category=self.income_sales,
            description="Sale",
        )
        create_transfer(
            date=date(2026, 10, 8),
            amount=Decimal("10000"),
            source=self.sbi,
            destination=self.hdfc,
            description="Internal",
        )
        dash = dashboard_summary(2026, 10)
        ie = income_expense_totals(2026, 10)
        bva = budget_vs_actual(2026, 10)
        self.assertEqual(dash["total_income"], ie["income"])
        self.assertEqual(dash["total_expenses"], ie["expenses"])
        self.assertEqual(dash["net_cash_flow"], ie["net_cash_flow"])
        self.assertEqual(dash["total_expense_budget"], bva["total_budget"])
        self.assertEqual(dash["actual_expenses"], Decimal("2500.00"))
        self.assertEqual(expenses_by_category(2026, 10)[0]["actual"], Decimal("2500.00"))
        self.assertEqual(ie["income"], Decimal("15000.00"))

        self.login()
        self.client.get(reverse("finance:dashboard") + "?year=2026&month=10")
        response = self.client.get(reverse("finance:reports") + "?year=2026&month=10")
        self.assertContains(response, "₹15,000.00")
        self.assertContains(response, "₹2,500.00")
        csv_response = self.client.get(reverse("finance:reports") + "?year=2026&month=10&export=csv&report=income")
        self.assertEqual(csv_response.status_code, 200)
        self.assertIn(b"15000", csv_response.content)
