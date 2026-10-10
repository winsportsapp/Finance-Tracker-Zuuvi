from calendar import monthrange
from datetime import date

from django.utils import timezone

MONTH_CHOICES = [
    (1, "January"),
    (2, "February"),
    (3, "March"),
    (4, "April"),
    (5, "May"),
    (6, "June"),
    (7, "July"),
    (8, "August"),
    (9, "September"),
    (10, "October"),
    (11, "November"),
    (12, "December"),
]


def month_name(month: int) -> str:
    return dict(MONTH_CHOICES).get(month, str(month))


def month_bounds(year: int, month: int) -> tuple[date, date]:
    last_day = monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last_day)


def parse_int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def get_selected_period(request) -> tuple[int, int]:
    today = timezone.localdate()
    year = parse_int(
        request.GET.get("year") or request.session.get("period_year"),
        today.year,
    )
    month = parse_int(
        request.GET.get("month") or request.session.get("period_month"),
        today.month,
    )
    if not 1 <= month <= 12:
        month = today.month
    if year < 2000 or year > 2100:
        year = today.year
    request.session["period_year"] = year
    request.session["period_month"] = month
    return year, month
