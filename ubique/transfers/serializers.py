from rest_framework import serializers

from ubique.wallets.models import PaymentCard

from .models import LedgerEntry, Transfer


class LedgerEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = LedgerEntry
        fields = ["account", "direction", "amount", "currency", "created_at"]


class TransferSerializer(serializers.ModelSerializer):
    ledger_entries = LedgerEntrySerializer(many=True, read_only=True)
    approval = serializers.SerializerMethodField()

    class Meta:
        model = Transfer
        fields = [
            "id", "status", "send_amount", "send_currency", "receive_currency",
            "recipient_card_last4", "recipient_reference", "network",
            "usdt_transferred", "receive_amount", "commission", "network_fee_usdt",
            "payin_ref", "chain_tx", "payout_ref", "failure_reason",
            "created_at", "approval", "ledger_entries",
        ]

    def get_approval(self, obj):
        a = getattr(obj, "onchain_approval", None)
        if a is None:
            return None
        return {"approvals": a.approval_count(), "threshold": a.threshold,
                "satisfied": a.is_satisfied()}


class CreateTransferSerializer(serializers.Serializer):
    source_card_id = serializers.IntegerField()
    # Recipient: a saved recipient, a fresh card number, or (legacy) last 4.
    recipient_id = serializers.IntegerField(required=False)
    recipient_card_number = serializers.CharField(required=False, allow_blank=True)
    recipient_card_last4 = serializers.CharField(max_length=4, required=False, allow_blank=True)
    recipient_name = serializers.CharField(max_length=128, required=False, allow_blank=True)
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

    def validate(self, attrs):
        if not (attrs.get("recipient_id") or attrs.get("recipient_card_number")
                or attrs.get("recipient_card_last4")):
            raise serializers.ValidationError(
                "Provide recipient_id, recipient_card_number or recipient_card_last4."
            )
        return attrs
