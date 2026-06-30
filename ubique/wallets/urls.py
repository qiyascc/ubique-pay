from django.urls import path

from .views import (
    CryptoAccountDetail,
    CryptoAccountListCreate,
    PaymentCardDetail,
    PaymentCardListCreate,
    RecipientDetail,
    RecipientListCreate,
)

urlpatterns = [
    path("cards/", PaymentCardListCreate.as_view(), name="card-list"),
    path("cards/<int:pk>/", PaymentCardDetail.as_view(), name="card-detail"),
    path("crypto/", CryptoAccountListCreate.as_view(), name="crypto-list"),
    path("crypto/<int:pk>/", CryptoAccountDetail.as_view(), name="crypto-detail"),
    path("recipients/", RecipientListCreate.as_view(), name="recipient-list"),
    path("recipients/<int:pk>/", RecipientDetail.as_view(), name="recipient-detail"),
]
