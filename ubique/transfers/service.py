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

from ubique.providers import registry
from ubique.quotes.engine import build_quote

from .models import LedgerEntry, Transfer
from .state import Status, can_transition


class KycRequired(Exception):
    pass


class LimitExceeded(Exception):
    pass


class ComplianceReject(Exception):
    pass


class LiquidityError(Exception):
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
                    send_amount, send_currency, receive_currency, idempotency_key):
    existing = Transfer.objects.filter(idempotency_key=idempotency_key).first()
    if existing:
        return existing

    _screen(user, recipient_card_last4)
    _check_velocity(user, send_amount)

    quote = build_quote(
        send_amount=send_amount, send_currency=send_currency,
        receive_currency=receive_currency,
    )
    transfer = Transfer.objects.create(
        user=user, idempotency_key=idempotency_key,
        send_amount=quote.send_amount, send_currency=quote.send_currency,
        receive_currency=quote.receive_currency, source_card=source_card,
        recipient_card_last4=recipient_card_last4,
        recipient_reference=recipient_reference, network=quote.network,
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

    _check_liquidity(transfer)

    try:
        _initiate_payin(transfer)
    except (KycRequired, LimitExceeded, ComplianceReject, LiquidityError):
        raise
    except Exception as exc:  # noqa: BLE001
        fail(transfer, str(exc))
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
    _do_onchain_and_payout(transfer)


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
        destination_card=transfer.recipient_card_last4,
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
    if settings.UBIQUE.get("LIQUIDITY_ENFORCED"):
        from django.db.models import F

        from ubique.corridors.models import TreasuryBalance
        TreasuryBalance.objects.filter(currency=transfer.receive_currency).update(
            available=F("available") - transfer.receive_amount
        )


def fail(transfer, reason):
    if can_transition(transfer.status, Status.FAILED):
        transfer.advance(Status.FAILED, failure_reason=reason[:255])
