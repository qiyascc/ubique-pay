from django.urls import path

from .views import TransferDetail, TransferListCreate
from .webhooks import OnRampWebhook, PayoutWebhook

urlpatterns = [
    path("", TransferListCreate.as_view(), name="transfer-list"),
    path("<int:pk>/", TransferDetail.as_view(), name="transfer-detail"),
    path("webhooks/onramp/", OnRampWebhook.as_view(), name="webhook-onramp"),
    path("webhooks/payout/", PayoutWebhook.as_view(), name="webhook-payout"),
]
