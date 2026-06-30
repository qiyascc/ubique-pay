"""Transfer orchestration: quote -> pay-in -> on-chain -> payout.

With the mock providers the whole chain settles synchronously. Real providers
are asynchronous; the same `advance()` calls would be driven by their webhooks.
Every step is idempotent and writes to the ledger.
"""

from django.db import transaction

from ubique.providers import registry
from ubique.quotes.engine import build_quote

from .models import LedgerEntry, Transfer
from .state import Status


class KycRequired(Exception):
    pass


def create_transfer(*, user, source_card, recipient_card_last4, recipient_reference,
                    send_amount, send_currency, receive_currency, idempotency_key):
    existing = Transfer.objects.filter(idempotency_key=idempotency_key).first()
    if existing:
        return existing

    quote = build_quote(
        send_amount=send_amount,
        send_currency=send_currency,
        receive_currency=receive_currency,
    )
    transfer = Transfer.objects.create(
        user=user,
        idempotency_key=idempotency_key,
        send_amount=quote.send_amount,
        send_currency=quote.send_currency,
        receive_currency=quote.receive_currency,
        source_card=source_card,
        recipient_card_last4=recipient_card_last4,
        recipient_reference=recipient_reference,
        network=quote.network,
        usdt_transferred=quote.usdt_transferred,
        receive_amount=quote.receive_amount,
        commission=quote.commission,
        network_fee_usdt=quote.network_fee_usdt,
    )
    transfer.advance(Status.QUOTED)
    return transfer


def _ledger(transfer, account, direction, amount, currency):
    LedgerEntry.objects.create(
        transfer=transfer, account=account, direction=direction,
        amount=amount, currency=currency,
    )


@transaction.atomic
def execute(transfer_id):
    transfer = Transfer.objects.select_for_update().get(pk=transfer_id)

    if transfer.status == Status.COMPLETED:
        return transfer
    if not transfer.user.is_kyc_verified:
        raise KycRequired("Sender must complete KYC before transferring.")
    if transfer.status != Status.QUOTED:
        return transfer  # nothing to do / already in flight

    key = transfer.idempotency_key
    try:
        # 1) Pay-in: charge the card, receive USDT into treasury.
        transfer.advance(Status.PAYIN_PENDING)
        payin = registry.onramp().create_payin(
            amount=transfer.send_amount, currency=transfer.send_currency,
            card_token=transfer.source_card.provider_token, idempotency_key=f"{key}:in",
        )
        transfer.advance(Status.PAYIN_SETTLED, payin_ref=payin.provider_ref)
        _ledger(transfer, "treasury_usdt", "credit", transfer.usdt_transferred, "USDT")
        _ledger(transfer, "ubique_revenue", "credit", transfer.commission, transfer.send_currency)

        # 2) On-chain: move USDT over the cheapest network to the payout pool.
        chain = registry.chain_sender().send(
            network=transfer.network, to_address="payout-pool",
            usdt_amount=transfer.usdt_transferred, idempotency_key=f"{key}:chain",
        )
        transfer.advance(Status.ONCHAIN_SENT, chain_tx=chain.tx_hash)
        _ledger(transfer, "treasury_usdt", "debit", transfer.usdt_transferred, "USDT")
        _ledger(transfer, "payout_pool", "credit", transfer.usdt_transferred, "USDT")

        # 3) Payout: push local fiat to the recipient's card.
        transfer.advance(Status.PAYOUT_PENDING)
        payout = registry.payout().create_payout(
            amount=transfer.receive_amount, currency=transfer.receive_currency,
            destination_card=transfer.recipient_card_last4, idempotency_key=f"{key}:out",
        )
        transfer.advance(Status.COMPLETED, payout_ref=payout.provider_ref)
        _ledger(transfer, "payout_pool", "debit", transfer.usdt_transferred, "USDT")
        _ledger(transfer, "recipient_card", "credit", transfer.receive_amount, transfer.receive_currency)
    except KycRequired:
        raise
    except Exception as exc:  # noqa: BLE001 - record the failure, surface it
        transfer.advance(Status.FAILED, failure_reason=str(exc)[:255])
        raise

    return transfer
