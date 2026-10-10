from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from finance.views import OwnerLoginView, OwnerLogoutView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("login/", OwnerLoginView.as_view(), name="login"),
    path("logout/", OwnerLogoutView.as_view(), name="logout"),
    path("", include("finance.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
