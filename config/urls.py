from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from ubique.common import health

api_v1 = [
    path("auth/", include("ubique.accounts.urls")),
    path("wallets/", include("ubique.wallets.urls")),
    path("quotes/", include("ubique.quotes.urls")),
    path("transfers/", include("ubique.transfers.urls")),
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="v1:schema"), name="docs"),
]

urlpatterns = [
    path("healthz", health.healthz, name="healthz"),
    path("readyz", health.readyz, name="readyz"),
    path("admin/", admin.site.urls),
    path("api/v1/", include((api_v1, "v1"))),
    path("", include("ubique.web.urls")),
]
