from django.urls import path

from .views import (
    KycStartView,
    KycTokenView,
    MeView,
    RequestOtpView,
    SumsubWebhookView,
    TelegramAuthView,
    VerifyOtpView,
)

urlpatterns = [
    path("request-otp/", RequestOtpView.as_view(), name="request-otp"),
    path("verify-otp/", VerifyOtpView.as_view(), name="verify-otp"),
    path("telegram/", TelegramAuthView.as_view(), name="telegram-auth"),
    path("me/", MeView.as_view(), name="me"),
    path("kyc/start/", KycStartView.as_view(), name="kyc-start"),
    path("kyc/token/", KycTokenView.as_view(), name="kyc-token"),
    path("kyc/webhook/", SumsubWebhookView.as_view(), name="kyc-webhook"),
]
