from rest_framework import serializers

from .models import CryptoAccount, PaymentCard


class PaymentCardSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentCard
        fields = ["id", "provider_token", "brand", "last4", "is_default", "created_at"]
        read_only_fields = ["id", "created_at"]
        extra_kwargs = {
            # In production this is a token from the card-vault SDK; allow blank
            # so a demo/placeholder token can be generated server-side.
            "provider_token": {"write_only": True, "required": False, "allow_blank": True},
        }


class CryptoAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = CryptoAccount
        fields = ["id", "network", "address", "created_at"]
        read_only_fields = ["id", "created_at"]
