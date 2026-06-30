from django.urls import path

from .views import MeView, RequestOtpView, VerifyOtpView

urlpatterns = [
    path("request-otp/", RequestOtpView.as_view(), name="request-otp"),
    path("verify-otp/", VerifyOtpView.as_view(), name="verify-otp"),
    path("me/", MeView.as_view(), name="me"),
]
