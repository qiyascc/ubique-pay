from django.urls import path

from .views import TransferDetail, TransferListCreate

urlpatterns = [
    path("", TransferListCreate.as_view(), name="transfer-list"),
    path("<int:pk>/", TransferDetail.as_view(), name="transfer-detail"),
]
