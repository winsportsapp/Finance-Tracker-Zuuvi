from django.urls import path

from . import views

app_name = "finance"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("transactions/", views.transaction_list, name="transaction_list"),
    path("transactions/add/", views.transaction_create, name="transaction_create"),
    path("transactions/<int:pk>/", views.transaction_detail, name="transaction_detail"),
    path("transactions/<int:pk>/edit/", views.transaction_edit, name="transaction_edit"),
    path("transactions/<int:pk>/delete/", views.transaction_delete, name="transaction_delete"),
    path("transfers/add/", views.transfer_create, name="transfer_create"),
    path("transfers/<uuid:group>/edit/", views.transfer_edit, name="transfer_edit"),
    path("transfers/<uuid:group>/delete/", views.transfer_delete, name="transfer_delete"),
    path("budgets/", views.budget_list, name="budget_list"),
    path("budgets/add/", views.budget_create, name="budget_create"),
    path("budgets/<int:pk>/edit/", views.budget_edit, name="budget_edit"),
    path("budgets/<int:pk>/delete/", views.budget_delete, name="budget_delete"),
    path("categories/", views.category_list, name="category_list"),
    path("categories/add/", views.category_create, name="category_create"),
    path("categories/<int:pk>/edit/", views.category_edit, name="category_edit"),
    path("categories/<int:pk>/delete/", views.category_delete, name="category_delete"),
    path("accounts/", views.account_list, name="account_list"),
    path("accounts/add/", views.account_create, name="account_create"),
    path("accounts/<int:pk>/", views.account_detail, name="account_detail"),
    path("accounts/<int:pk>/edit/", views.account_edit, name="account_edit"),
    path("accounts/<int:pk>/delete/", views.account_delete, name="account_delete"),
    path("reports/", views.reports, name="reports"),
    path("settings/", views.settings_view, name="settings"),
]
