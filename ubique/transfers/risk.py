"""Pluggable AML / risk-scoring engine.

Each rule looks at a transfer-in-creation and returns ``(score, reason)``. The
engine sums the scores and maps the total to a decision:

    score >= RISK_BLOCK_THRESHOLD  -> block (rejected outright)
    score >= RISK_REVIEW_THRESHOLD -> review (held for a compliance officer)
    otherwise                      -> allow

Rules are configured via ``UBIQUE["RISK_RULES"]`` (dotted paths), so corridors
or jurisdictions can layer on their own checks.
"""

from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.utils import timezone
from django.utils.module_loading import import_string


@dataclass
class RiskResult:
    score: int
    decision: str  # "allow" | "review" | "block"
    reasons: list = field(default_factory=list)


def high_amount(user, ctx):
    cfg = settings.UBIQUE
    amount = Decimal(str(ctx["send_amount"]))
    if amount >= Decimal(str(cfg["RISK_BLOCK_AMOUNT"])):
        return 100, f"amount >= {cfg['RISK_BLOCK_AMOUNT']}"
    if amount >= Decimal(str(cfg["RISK_REVIEW_AMOUNT"])):
        return 50, f"amount >= {cfg['RISK_REVIEW_AMOUNT']}"
    return 0, None


def new_recipient(user, ctx):
    from .models import Transfer
    seen = Transfer.objects.filter(
        user=user, recipient_card_last4=ctx["recipient_last4"]
    ).exists()
    return (0, None) if seen else (20, "new recipient")


def rapid_velocity(user, ctx):
    from .models import Transfer
    window = timezone.now() - timedelta(hours=1)
    count = Transfer.objects.filter(user=user, created_at__gte=window).count()
    cap = settings.UBIQUE["RISK_HOURLY_COUNT"]
    return (40, f">{cap} transfers/hour") if count >= cap else (0, None)


def evaluate(user, ctx) -> RiskResult:
    cfg = settings.UBIQUE
    score = 0
    reasons = []
    for path in cfg["RISK_RULES"]:
        rule_score, reason = import_string(path)(user, ctx)
        score += rule_score
        if reason:
            reasons.append(reason)

    if score >= cfg["RISK_BLOCK_THRESHOLD"]:
        decision = "block"
    elif score >= cfg["RISK_REVIEW_THRESHOLD"]:
        decision = "review"
    else:
        decision = "allow"
    return RiskResult(score=score, decision=decision, reasons=reasons)
