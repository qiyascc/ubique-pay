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


class PaymentCardDetail(_OwnedMixin, generics.RetrieveDestroyAPIView):
    model = PaymentCard
    serializer_class = PaymentCardSerializer


class CryptoAccountListCreate(_OwnedMixin, generics.ListCreateAPIView):
    model = CryptoAccount
    serializer_class = CryptoAccountSerializer


class CryptoAccountDetail(_OwnedMixin, generics.RetrieveDestroyAPIView):
    model = CryptoAccount
    serializer_class = CryptoAccountSerializer
