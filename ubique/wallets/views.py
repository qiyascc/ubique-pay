import uuid

from rest_framework import generics

from .models import CryptoAccount, PaymentCard
from .serializers import CryptoAccountSerializer, PaymentCardSerializer


class _OwnedMixin:
    def get_queryset(self):
        return self.model.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class PaymentCardListCreate(_OwnedMixin, generics.ListCreateAPIView):
    model = PaymentCard
    serializer_class = PaymentCardSerializer

    def perform_create(self, serializer):
        token = serializer.validated_data.get("provider_token") or f"tok_{uuid.uuid4().hex[:12]}"
        serializer.save(user=self.request.user, provider_token=token)


class PaymentCardDetail(_OwnedMixin, generics.RetrieveDestroyAPIView):
    model = PaymentCard
    serializer_class = PaymentCardSerializer


class CryptoAccountListCreate(_OwnedMixin, generics.ListCreateAPIView):
    model = CryptoAccount
    serializer_class = CryptoAccountSerializer


class CryptoAccountDetail(_OwnedMixin, generics.RetrieveDestroyAPIView):
    model = CryptoAccount
    serializer_class = CryptoAccountSerializer
