"""Transfer state machine."""

from django.db import models


class Status(models.TextChoices):
    CREATED = "created", "Created"
    QUOTED = "quoted", "Quoted"
    PAYIN_PENDING = "payin_pending", "Pay-in pending"
    PAYIN_SETTLED = "payin_settled", "Pay-in settled (USDT received)"
    ONCHAIN_SENT = "onchain_sent", "On-chain transfer sent"
    PAYOUT_PENDING = "payout_pending", "Payout pending"
    COMPLETED = "completed", "Completed"
    FAILED = "failed", "Failed"
    REFUNDED = "refunded", "Refunded"


# Allowed forward transitions.
TRANSITIONS = {
    Status.CREATED: {Status.QUOTED, Status.FAILED},
    Status.QUOTED: {Status.PAYIN_PENDING, Status.FAILED},
    Status.PAYIN_PENDING: {Status.PAYIN_SETTLED, Status.FAILED},
    Status.PAYIN_SETTLED: {Status.ONCHAIN_SENT, Status.FAILED},
    Status.ONCHAIN_SENT: {Status.PAYOUT_PENDING, Status.FAILED},
    Status.PAYOUT_PENDING: {Status.COMPLETED, Status.FAILED},
    Status.FAILED: {Status.REFUNDED},
    Status.COMPLETED: set(),
    Status.REFUNDED: set(),
}


class InvalidTransition(Exception):
    pass


def can_transition(current, target) -> bool:
    return target in TRANSITIONS.get(current, set())
