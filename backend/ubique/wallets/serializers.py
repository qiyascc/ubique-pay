from rest_framework import serializers

from .models import CryptoAccount, PaymentCard


class PaymentCardSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentCard
        fields = ["id", "provider_token", "brand", "last4", "is_default", "created_at"]
        read_only_fields = ["id", "created_at"]
        extra_kwargs = {"provider_token": {"write_only": True}}


class CryptoAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = CryptoAccount
        fields = ["id", "network", "address", "created_at"]
        read_only_fields = ["id", "created_at"]
