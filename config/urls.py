from django.contrib import admin
from django.urls import include, path

api_v1 = [
    path("auth/", include("ubique.accounts.urls")),
    path("wallets/", include("ubique.wallets.urls")),
    path("quotes/", include("ubique.quotes.urls")),
    path("transfers/", include("ubique.transfers.urls")),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include((api_v1, "v1"))),
    path("", include("ubique.web.urls")),
]
