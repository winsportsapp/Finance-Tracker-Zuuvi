from .models import CompanySettings
from .period import MONTH_CHOICES, get_selected_period, month_name
from .services import year_choices


def company_settings(request):
    if not request.user.is_authenticated:
        return {}
    settings = CompanySettings.get_solo()
    return {"company": settings}


def selected_period(request):
    if not request.user.is_authenticated:
        return {}
    year, month = get_selected_period(request)
    return {
        "period_year": year,
        "period_month": month,
        "period_label": f"{month_name(month)} {year}",
        "month_choices": MONTH_CHOICES,
        "year_choices": year_choices(),
    }
