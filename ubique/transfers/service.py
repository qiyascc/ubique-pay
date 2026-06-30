"""Transfer orchestration.

A real payment rail is asynchronous. The same internal step functions are used
two ways:

* **Synchronous providers** (the mocks) settle instantly, so `execute()` drives
  pay-in → on-chain → payout inline.
* **Real providers** return `pending`; the flow stops and is resumed by signed
  provider **webhooks** (`settle_payin`, `complete_payout`).

Every step is guarded by the current status (idempotent), and every money
movement writes a double-entry ledger row.
"""

from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from ubique.audit.log import log as audit_log
from ubique.common.notify import dispatch as notify_user
from ubique.providers import registry
from ubique.quotes.engine import build_quote

from .models import LedgerEntry, Transfer
from .outbound import enqueue as emit_event
from .state import Status, can_transition


def _event_payload(transfer):
    return {
        "transfer_id": transfer.id,
        "status": transfer.status,
        "send_amount": str(transfer.send_amount),
        "send_currency": transfer.send_currency,
        "receive_amount": str(transfer.receive_amount),
        "receive_currency": transfer.receive_currency,
    }


class KycRequired(Exception):
    pass


class LimitExceeded(Exception):
    pass


class ComplianceReject(Exception):
    pass


class LiquidityError(Exception):
    pass


class NotASigner(Exception):
    pass


class ReviewRequired(Exception):
    pass


# --- compliance / risk ----------------------------------------------------
def _screen(user, recipient_last4):
    deny = set(settings.UBIQUE.get("DENYLIST", []))
    if user.phone in deny or recipient_last4 in deny:
        raise ComplianceReject("Blocked by sanctions/compliance screening.")


def _check_velocity(user, amount):
    since = timezone.now() - timedelta(hours=24)
    used = (
        Transfer.objects.filter(user=user, created_at__gte=since)
        .exclude(status=Status.FAILED)
        .aggregate(s=Sum("send_amount"))["s"]
        or 0
    )
    cap = settings.UBIQUE["MAX_DAILY"]
    if float(used) + float(amount) > cap:
        raise LimitExceeded(f"Daily limit of {cap} exceeded.")


def _check_liquidity(transfer):
    if not settings.UBIQUE.get("LIQUIDITY_ENFORCED"):
        return
    from ubique.corridors.models import TreasuryBalance

    bal = TreasuryBalance.objects.filter(currency=transfer.receive_currency).first()
    if bal is None or bal.available < transfer.receive_amount:
        raise LiquidityError(
            f"Insufficient {transfer.receive_currency} payout float."
        )


# --- ledger ---------------------------------------------------------------
def _ledger(transfer, account, direction, amount, currency):
    LedgerEntry.objects.create(
        transfer=transfer, account=account, direction=direction,
        amount=amount, currency=currency,
    )


# --- creation -------------------------------------------------------------
def create_transfer(*, user, source_card, recipient_card_last4, recipient_reference,
                    send_amount, send_currency, receive_currency, idempotency_key,
                    recipient_card_token="", recipient_brand=""):
    existing = Transfer.objects.filter(idempotency_key=idempotency_key).first()
    if existing:
        return existing

    _screen(user, recipient_card_last4)
    _check_velocity(user, send_amount)

    from . import risk
    assessment = risk.evaluate(user, {
        "send_amount": send_amount, "recipient_last4": recipient_card_last4,
        "send_currency": send_currency, "receive_currency": receive_currency,
    })
    if assessment.decision == "block":
        raise ComplianceReject("Blocked by risk policy: " + ", ".join(assessment.reasons))

    quote = build_quote(
        send_amount=send_amount, send_currency=send_currency,
        receive_currency=receive_currency,
    )
    transfer = Transfer.objects.create(
        user=user, idempotency_key=idempotency_key,
        send_amount=quote.send_amount, send_currency=quote.send_currency,
        receive_currency=quote.receive_currency, source_card=source_card,
        recipient_card_last4=recipient_card_last4,
        recipient_card_token=recipient_card_token, recipient_brand=recipient_brand,
        recipient_reference=recipient_reference, network=quote.network,
        risk_score=assessment.score, risk_decision=assessment.decision,
        risk_reasons=", ".join(assessment.reasons)[:255],
        usdt_transferred=quote.usdt_transferred, receive_amount=quote.receive_amount,
        commission=quote.commission, network_fee_usdt=quote.network_fee_usdt,
    )
    transfer.advance(Status.QUOTED)
    return transfer


# --- execution / steps ----------------------------------------------------
@transaction.atomic
def execute(transfer_id):
    """Kick off a quoted transfer. Synchronous providers complete inline;
    asynchronous ones stop at PAYIN_PENDING and resume via webhooks."""
    transfer = Transfer.objects.select_for_update().get(pk=transfer_id)
    if transfer.status == Status.COMPLETED:
        return transfer
    if not transfer.user.is_kyc_verified:
        raise KycRequired("Sender must complete KYC before transferring.")
    if transfer.status != Status.QUOTED:
        return transfer
    if transfer.risk_decision == "review" and not transfer.review_released:
        raise ReviewRequired("Transfer held for compliance review.")

    _check_liquidity(transfer)

    try:
        _initiate_payin(transfer)
    except (KycRequired, LimitExceeded, ComplianceReject, LiquidityError):
        raise
    except Exception as exc:  # noqa: BLE001
        fail_and_refund(transfer, str(exc))
        raise
    return transfer


def _initiate_payin(transfer):
    transfer.advance(Status.PAYIN_PENDING)
    payin = registry.onramp().create_payin(
        amount=transfer.send_amount, currency=transfer.send_currency,
        card_token=transfer.source_card.provider_token,
        idempotency_key=f"{transfer.idempotency_key}:in",
    )
    transfer.payin_ref = payin.provider_ref
    transfer.save(update_fields=["payin_ref"])
    if payin.status == "settled":  # synchronous provider
        settle_payin(transfer)


def settle_payin(transfer):
    """Pay-in confirmed (inline for mocks, or by webhook for real providers)."""
    if transfer.status != Status.PAYIN_PENDING:
        return
    transfer.advance(Status.PAYIN_SETTLED)
    _ledger(transfer, "treasury_usdt", "credit", transfer.usdt_transferred, "USDT")
    _ledger(transfer, "ubique_revenue", "credit", transfer.commission, transfer.send_currency)
    _after_payin(transfer)


def _needs_approval(transfer):
    cfg = settings.UBIQUE
    return bool(cfg.get("MULTISIG_ENABLED")) and \
        float(transfer.usdt_transferred) >= cfg["MULTISIG_MIN_USDT"]


def _after_payin(transfer):
    """Either gate the on-chain move behind multisig approval, or run it now."""
    if _needs_approval(transfer):
        from .models import OnchainApproval
        transfer.advance(Status.APPROVAL_PENDING)
        OnchainApproval.objects.get_or_create(
            transfer=transfer,
            defaults={"threshold": settings.UBIQUE["MULTISIG_THRESHOLD"]},
        )
    else:
        _do_onchain_and_payout(transfer)


def approve_onchain(transfer, signer):
    """Record a treasury signer's approval; broadcast once the threshold is met."""
    if not getattr(signer, "is_treasury_signer", False):
        raise NotASigner("Only treasury signers can approve.")
    if transfer.status != Status.APPROVAL_PENDING:
        return transfer
    approval = transfer.onchain_approval
    approval.approvers.add(signer)
    audit_log("approval.granted", actor=signer, target=f"transfer:{transfer.id}",
              approvals=approval.approval_count(), threshold=approval.threshold)
    if approval.is_satisfied():
        _do_onchain_and_payout(transfer)
    return transfer


def _do_onchain_and_payout(transfer):
    chain = registry.chain_sender().send(
        network=transfer.network, to_address="payout-pool",
        usdt_amount=transfer.usdt_transferred,
        idempotency_key=f"{transfer.idempotency_key}:chain",
    )
    transfer.advance(Status.ONCHAIN_SENT, chain_tx=chain.tx_hash)
    _ledger(transfer, "treasury_usdt", "debit", transfer.usdt_transferred, "USDT")
    _ledger(transfer, "payout_pool", "credit", transfer.usdt_transferred, "USDT")

    transfer.advance(Status.PAYOUT_PENDING)
    payout = registry.payout().create_payout(
        amount=transfer.receive_amount, currency=transfer.receive_currency,
        destination_card=transfer.recipient_card_token or transfer.recipient_card_last4,
        idempotency_key=f"{transfer.idempotency_key}:out",
    )
    transfer.payout_ref = payout.provider_ref
    transfer.save(update_fields=["payout_ref"])
    if payout.status == "paid":  # synchronous provider
        complete_payout(transfer)


def complete_payout(transfer):
    """Payout confirmed (inline for mocks, or by webhook for real providers)."""
    if transfer.status != Status.PAYOUT_PENDING:
        return
    transfer.advance(Status.COMPLETED)
    _ledger(transfer, "payout_pool", "debit", transfer.usdt_transferred, "USDT")
    _ledger(transfer, "recipient_card", "credit", transfer.receive_amount, transfer.receive_currency)
    audit_log("transfer.completed", target=f"transfer:{transfer.id}",
              amount=str(transfer.receive_amount), currency=transfer.receive_currency)
    emit_event("transfer.completed", _event_payload(transfer))
    notify_user(transfer.user, "transfer.completed",
                f"✅ {transfer.receive_amount} {transfer.receive_currency} sent to "
                f"····{transfer.recipient_card_last4}.")
    if settings.UBIQUE.get("LIQUIDITY_ENFORCED"):
        from django.db.models import F

        from ubique.corridors.models import TreasuryBalance
        TreasuryBalance.objects.filter(currency=transfer.receive_currency).update(
            available=F("available") - transfer.receive_amount
        )


def fail(transfer, reason):
    if can_transition(transfer.status, Status.FAILED):
        transfer.advance(Status.FAILED, failure_reason=reason[:255])
        audit_log("transfer.failed", target=f"transfer:{transfer.id}", reason=reason[:255])
        emit_event("transfer.failed", _event_payload(transfer))
        notify_user(transfer.user, "transfer.failed",
                    "⚠️ Your transfer could not be completed; no funds were moved.")


def refund(transfer):
    """Reverse a failed transfer back to the sender. Idempotent.

    If the pay-in had settled (the sender was actually charged) we ask the
    on-ramp provider to refund the card and write the reversing ledger entries;
    otherwise nothing was taken and we simply close the transfer.
    """
    if transfer.status != Status.FAILED:
        return transfer

    charged = transfer.ledger_entries.filter(
        account="treasury_usdt", direction="credit"
    ).exists()
    if charged:
        result = registry.onramp().refund_payin(
            provider_ref=transfer.payin_ref, amount=transfer.send_amount,
            currency=transfer.send_currency,
            idempotency_key=f"{transfer.idempotency_key}:refund",
        )
        transfer.advance(Status.REFUNDED, refund_ref=result.provider_ref)
        _ledger(transfer, "sender_refund", "credit", transfer.send_amount, transfer.send_currency)
        # We don't keep the commission on a reversed transfer.
        _ledger(transfer, "ubique_revenue", "debit", transfer.commission, transfer.send_currency)
    else:
        transfer.advance(Status.REFUNDED)
    audit_log("transfer.refunded", target=f"transfer:{transfer.id}",
              amount=str(transfer.send_amount), currency=transfer.send_currency)
    emit_event("transfer.refunded", _event_payload(transfer))
    notify_user(transfer.user, "transfer.refunded",
                f"↩️ {transfer.send_amount} {transfer.send_currency} has been refunded.")
    return transfer


def fail_and_refund(transfer, reason):
    """Mark failed and immediately reverse any settled funds to the sender."""
    fail(transfer, reason)
    refund(transfer)


def release_for_review(transfer, officer):
    """A compliance officer clears a held transfer so it can proceed."""
    if transfer.risk_decision != "review" or transfer.review_released:
        return transfer
    transfer.review_released = True
    transfer.save(update_fields=["review_released"])
    audit_log("transfer.review_released", actor=officer, target=f"transfer:{transfer.id}",
              score=transfer.risk_score)
    return transfer


def open_dispute(transfer, reason, actor=None):
    from .models import Dispute
    dispute = Dispute.objects.create(transfer=transfer, reason=reason[:255])
    audit_log("dispute.opened", actor=actor, target=f"transfer:{transfer.id}",
              reason=reason[:120])
    return dispute


def resolve_dispute(dispute, outcome, officer, resolution=""):
    """Close a dispute. A chargeback records the lost funds in the ledger."""
    from .models import Dispute
    if dispute.status != Dispute.Status.OPEN:
        return dispute
    dispute.status = outcome
    dispute.resolution = resolution[:255]
    dispute.resolved_at = timezone.now()
    dispute.save()
    if outcome == Dispute.Status.CHARGED_BACK:
        transfer = dispute.transfer
        _ledger(transfer, "chargeback_loss", "debit",
                transfer.receive_amount, transfer.receive_currency)
    audit_log("dispute.resolved", actor=officer,
              target=f"transfer:{dispute.transfer_id}", outcome=outcome)
    return dispute
