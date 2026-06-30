from rest_framework import serializers

from .cards import tokenize_card
from .models import CryptoAccount, PaymentCard, Recipient


class RecipientSerializer(serializers.ModelSerializer):
    card_number = serializers.CharField(write_only=True)

    class Meta:
        model = Recipient
        fields = ["id", "name", "card_number", "brand", "last4", "created_at"]
        read_only_fields = ["id", "brand", "last4", "created_at"]

    def create(self, validated_data):
        number = validated_data.pop("card_number")
        try:
            token, last4, brand = tokenize_card(number)
        except ValueError as exc:
            raise serializers.ValidationError({"card_number": str(exc)}) from exc
        return Recipient.objects.create(
            card_token=token, last4=last4, brand=brand, **validated_data
        )


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
