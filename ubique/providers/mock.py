"""In-memory mock providers so the whole flow runs without real credentials.

Fees and rates mirror the figures gathered during research (see ARCHITECTURE.md):
TON is by far the cheapest USDT network, Solana slightly cheaper still, TRON the
most expensive for a typical (non-staked) transfer.
"""

import uuid
from decimal import Decimal

from .base import (
    ChainResult,
    ChainSender,
    FxOracle,
    NetworkFeeOracle,
    OnRampProvider,
    PayinResult,
    PayoutProvider,
    PayoutResult,
    RefundResult,
)


def _ref(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


class MockOnRampProvider(OnRampProvider):
    # ~2% card-acquiring fee, typical of instant-card on-ramps.
    fee_rate = Decimal("0.02")

    def create_payin(self, *, amount, currency, card_token, idempotency_key):
        usdt = (amount * (Decimal("1") - self.fee_rate)).quantize(Decimal("0.000001"))
        return PayinResult(provider_ref=_ref("payin"), status="settled", usdt_amount=usdt)

    def get_payin(self, provider_ref):
        return PayinResult(provider_ref=provider_ref, status="settled", usdt_amount=Decimal("0"))

    def refund_payin(self, *, provider_ref, amount, currency, idempotency_key):
        return RefundResult(provider_ref=_ref("refund"), status="refunded")


class MockChainSender(ChainSender):
    def send(self, *, network, to_address, usdt_amount, idempotency_key):
        return ChainResult(tx_hash=_ref("0x"), status="confirmed", network=network)

    def get_status(self, tx_hash, network):
        return ChainResult(tx_hash=tx_hash, status="confirmed", network=network)


class MockPayoutProvider(PayoutProvider):
    def create_payout(self, *, amount, currency, destination_card, idempotency_key):
        return PayoutResult(provider_ref=_ref("payout"), status="paid")

    def get_payout(self, provider_ref):
        return PayoutResult(provider_ref=provider_ref, status="paid")


class MockFxOracle(FxOracle):
    # A few illustrative mid-market rates (1 base = N quote).
    _RATES = {
        ("USDT", "USD"): Decimal("1.00"),
        ("USDT", "EUR"): Decimal("0.92"),
        ("USDT", "AZN"): Decimal("1.70"),
        ("USDT", "TRY"): Decimal("32.0"),
        ("USD", "USDT"): Decimal("1.00"),
        ("EUR", "USDT"): Decimal("1.087"),
        ("AZN", "USDT"): Decimal("0.588"),
        ("TRY", "USDT"): Decimal("0.03125"),
    }

    def rate(self, base, quote):
        if base == quote:
            return Decimal("1")
        try:
            return self._RATES[(base, quote)]
        except KeyError as exc:
            raise ValueError(f"No FX rate for {base}->{quote}") from exc


class MockNetworkFeeOracle(NetworkFeeOracle):
    # USDT-equivalent cost of a single transfer per network (research figures).
    _FEES = {
        "TON": Decimal("0.01"),
        "SOLANA": Decimal("0.001"),
        "TRON": Decimal("1.50"),
    }

    def fee_usdt(self, network):
        return self._FEES.get(network.upper(), Decimal("1.00"))
