from rest_framework import serializers

from ubique.wallets.models import PaymentCard

from .models import LedgerEntry, Transfer


class LedgerEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = LedgerEntry
        fields = ["account", "direction", "amount", "currency", "created_at"]


class TransferSerializer(serializers.ModelSerializer):
    ledger_entries = LedgerEntrySerializer(many=True, read_only=True)

    class Meta:
        model = Transfer
        fields = [
            "id", "status", "send_amount", "send_currency", "receive_currency",
            "recipient_card_last4", "recipient_reference", "network",
            "usdt_transferred", "receive_amount", "commission", "network_fee_usdt",
            "payin_ref", "chain_tx", "payout_ref", "failure_reason",
            "created_at", "ledger_entries",
        ]


class CreateTransferSerializer(serializers.Serializer):
    source_card_id = serializers.IntegerField()
    recipient_card_last4 = serializers.CharField(max_length=4)
    recipient_reference = serializers.CharField(max_length=128, required=False, allow_blank=True)
    send_amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0)
    send_currency = serializers.CharField(max_length=8)
    receive_currency = serializers.CharField(max_length=8)
    idempotency_key = serializers.CharField(max_length=64)

    def validate_source_card_id(self, value):
        user = self.context["request"].user
        if not PaymentCard.objects.filter(id=value, user=user).exists():
            raise serializers.ValidationError("Card not found.")
        return value
