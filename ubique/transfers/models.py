from django.conf import settings
from django.db import models

from .state import Status, can_transition, InvalidTransition


class Transfer(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="transfers"
    )
    idempotency_key = models.CharField(max_length=64, unique=True)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.CREATED
    )

    # Order details.
    send_amount = models.DecimalField(max_digits=12, decimal_places=2)
    send_currency = models.CharField(max_length=8)
    receive_currency = models.CharField(max_length=8)
    source_card = models.ForeignKey(
        "wallets.PaymentCard", on_delete=models.PROTECT, related_name="transfers"
    )
    recipient_card_last4 = models.CharField(max_length=4)
    recipient_reference = models.CharField(max_length=128, blank=True)

    # Frozen quote snapshot.
    network = models.CharField(max_length=10)
    usdt_transferred = models.DecimalField(max_digits=18, decimal_places=6)
    receive_amount = models.DecimalField(max_digits=12, decimal_places=2)
    commission = models.DecimalField(max_digits=12, decimal_places=2)
    network_fee_usdt = models.DecimalField(max_digits=18, decimal_places=6)

    # Provider references.
    payin_ref = models.CharField(max_length=128, blank=True)
    chain_tx = models.CharField(max_length=128, blank=True)
    payout_ref = models.CharField(max_length=128, blank=True)
    failure_reason = models.CharField(max_length=255, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Transfer #{self.pk} ({self.status})"

    def advance(self, target, **fields):
        """Move to ``target`` if the transition is allowed, persisting fields."""
        if not can_transition(self.status, target):
            raise InvalidTransition(f"{self.status} -> {target} not allowed")
        self.status = target
        for key, value in fields.items():
            setattr(self, key, value)
        self.save()


class LedgerEntry(models.Model):
    """Append-only double-entry record of every money movement."""

    class Direction(models.TextChoices):
        DEBIT = "debit", "Debit"
        CREDIT = "credit", "Credit"

    transfer = models.ForeignKey(
        Transfer, on_delete=models.PROTECT, related_name="ledger_entries"
    )
    account = models.CharField(max_length=32)  # e.g. treasury_usdt, ubique_revenue
    direction = models.CharField(max_length=6, choices=Direction.choices)
    amount = models.DecimalField(max_digits=18, decimal_places=6)
    currency = models.CharField(max_length=8)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.direction} {self.amount} {self.currency} @ {self.account}"


class WebhookEvent(models.Model):
    """Raw inbound provider event — stored for idempotent processing & audit.

    A real payment rail is asynchronous: providers confirm pay-ins and payouts
    via webhooks, which may be retried. We dedupe on (provider, external_id) so
    a replayed event is never processed twice.
    """

    provider = models.CharField(max_length=32)
    external_id = models.CharField(max_length=128)
    event_type = models.CharField(max_length=64)
    payload = models.JSONField(default=dict)
    processed = models.BooleanField(default=False)
    attempts = models.PositiveIntegerField(default=0)
    error = models.TextField(blank=True)
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("provider", "external_id")
        ordering = ["-received_at"]

    def __str__(self):
        return f"{self.provider}:{self.event_type}:{self.external_id}"

    def is_dead_lettered(self, max_attempts):
        return not self.processed and self.attempts >= max_attempts


class OnchainApproval(models.Model):
    """Multisig gate for a treasury (on-chain) movement: requires ``threshold``
    approvals from treasury signers before the USDT is broadcast."""

    transfer = models.OneToOneField(
        Transfer, on_delete=models.CASCADE, related_name="onchain_approval"
    )
    threshold = models.PositiveIntegerField()
    approvers = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name="onchain_approvals"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def approval_count(self):
        return self.approvers.count()

    def is_satisfied(self):
        return self.approvers.count() >= self.threshold

    def __str__(self):
        return f"Approval for #{self.transfer_id} ({self.approval_count()}/{self.threshold})"
