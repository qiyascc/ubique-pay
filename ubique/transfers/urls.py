from django.urls import path

from .views import (
    TransferApproveView,
    TransferDetail,
    TransferListCreate,
    TransferReleaseView,
)
from .webhooks import OnRampWebhook, PayoutWebhook

urlpatterns = [
    path("", TransferListCreate.as_view(), name="transfer-list"),
    path("<int:pk>/", TransferDetail.as_view(), name="transfer-detail"),
    path("<int:pk>/approve/", TransferApproveView.as_view(), name="transfer-approve"),
    path("<int:pk>/release/", TransferReleaseView.as_view(), name="transfer-release"),
    path("webhooks/onramp/", OnRampWebhook.as_view(), name="webhook-onramp"),
    path("webhooks/payout/", PayoutWebhook.as_view(), name="webhook-payout"),
]
