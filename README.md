# Zuuvi Finance Tracker

Internal web application for a small service-provider business to record income and expenses, set monthly category budgets, manage bank and cash accounts, and compare actual spending against the plan.

This is not a public customer website and it does not connect to real banks.

## What it answers

- How much is budgeted this month?
- How much has been spent so far?
- How much budget remains?
- Which categories are overspent or near their limit?
- How much income has the business received?
- What are the current bank and cash balances?
- What is net cash flow (income − expenses)?
- Roughly how much is needed to run the business next month? (this month’s expense budget, or actual expenses if no budget exists)

**Remaining budget is not cash in the bank.** The dashboard shows those two figures separately.

## Requirements

- Python 3.12 or later (tested with Python 3.14)
- Django 6.1

## Install and run locally

```bash
cd "c:\Arun\Work Zuuvi\Zuuvi Finance Tracker"
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py seed_defaults
python manage.py createsuperuser
python manage.py runserver
```

Open [http://127.0.0.1:8000/](http://127.0.0.1:8000/) and sign in with the administrator account.

`seed_defaults` creates suggested income/expense categories, sample account names (SBI, HDFC, Cash, Petty Cash, UPI), and company settings. You can change or deactivate these later. Set each account’s opening balance to match your books.

Additional staff users can be added later from Django Admin (`/admin/`) using the same login system.

## Run tests

```bash
python manage.py test finance
```

## Business rules

1. Budgets apply to **expense** categories for a calendar month and year. Only one budget per category per month.
2. Only **debit** operating transactions on expense categories count toward expense budgets and expense totals.
3. Only **credit** operating transactions on income categories count toward income totals.
4. **Internal transfers** create a paired debit and credit on two accounts. They change account balances but do **not** count as income, expense, or budget activity.
5. Account current balance:

   `Opening balance + credits on/after the opening-balance date − debits on/after that date`

   Transactions dated **before** the opening-balance date are excluded from the current balance. They are treated as already included in the opening balance. They still appear in the transaction list and still affect income/expense/budget reports if they fall in the selected month.
6. Editing or deleting a transaction (or transfer) recalculates totals from stored records. Nothing is cached as a hard-coded dashboard number.
7. Money is stored as `Decimal` with two decimal places, never as floating-point.
8. Transfers are saved in a database transaction so both legs succeed or fail together.
9. Pages except login require authentication. Forms use Django CSRF protection.
10. The selected month/year is stored in the session and reused on the dashboard, budgets, and reports.

### Budget status

- Within Budget: below the warning threshold (default 90%)
- Near Limit: from the warning threshold up to but not including 100%
- Fully Used: exactly 100%
- Overspent: above 100%

Unbudgeted expense categories still appear, with status **No Budget**, so spending is not hidden.

## Manual testing checklist

- [ ] Unauthenticated visit to `/` redirects to login
- [ ] Wrong password shows a clear error; correct password opens the dashboard
- [ ] Logout returns to the login page
- [ ] Seeded categories and accounts appear
- [ ] Add a credit (income) and a debit (expense); dashboard income, expenses, and net cash flow update
- [ ] Expense category cannot be used on a credit; income category cannot be used on a debit
- [ ] Zero or negative amounts are rejected
- [ ] Create October budgets for several categories; table shows remaining amount and status
- [ ] Duplicate budget for the same category and month is rejected
- [ ] Spend past 90% (Near Limit), exactly 100% (Fully Used), and over 100% (Overspent)
- [ ] An expense with no budget still shows as No Budget
- [ ] Transfer from SBI to HDFC changes both balances and does not change income/expense/budget
- [ ] Edit and delete a transaction; balances and budget remaining update
- [ ] Transaction search, date range, type, category, account, sort, and pagination work
- [ ] Category used by a transaction cannot be deleted; it is deactivated
- [ ] Reports match the dashboard for the same month; CSV downloads open
- [ ] Settings: company name and 90% warning threshold affect the UI
- [ ] Layout is usable on a phone-width window (sidebar stacks)

## Project layout

- `config/` — Django project settings and URLs
- `finance/` — models, forms, calculation services, views, tests
- `templates/` — Django templates (Bootstrap 5)
- `static/css/app.css` — layout and dashboard styling
- `media/` — optional receipt uploads (local only)

Do not collect bank passwords, OTPs, or PINs. Receipt uploads are optional and limited to common document/image types up to 5 MB.
