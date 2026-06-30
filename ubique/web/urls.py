from django.urls import path

from . import views

app_name = "web"

urlpatterns = [
    path("", views.landing, name="landing"),
    path("login/", views.login_view, name="login"),
    path("verify/", views.verify_view, name="verify"),
    path("logout/", views.logout_view, name="logout"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("cards/add/", views.add_card, name="add_card"),
    path("recipients/", views.recipients, name="recipients"),
    path("kyc/verify/", views.verify_kyc, name="verify_kyc"),
    path("send/", views.send, name="send"),
    path("transfers/<int:pk>/", views.transfer_detail, name="transfer_detail"),
    path("statement.csv", views.statement_csv, name="statement_csv"),
    path("ops/", views.ops_dashboard, name="ops"),
    # Telegram Mini App
    path("app/", views.miniapp, name="miniapp"),
    path("tonconnect-manifest.json", views.tonconnect_manifest, name="tonconnect_manifest"),
]
