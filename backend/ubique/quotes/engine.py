"""Quote engine — fee breakdown + cheapest-network routing.

    send_amount
      − on_ramp_fee
      − network_fee     (minimum across supported networks → chosen_network)
      − payout_fee
      − ubique_commission
    = recipient_receives  (converted send_ccy → receive_ccy at FX mid + spread)
"""

from dataclasses import asdict, dataclass
from decimal import Decimal

from django.conf import settings

from ubique.common.money import money, usdt
from ubique.providers import registry


@dataclass
class Quote:
    send_amount: Decimal
    send_currency: str
    receive_currency: str
    onramp_fee: Decimal
    network: str
    network_fee_usdt: Decimal
    payout_fee: Decimal
    commission: Decimal
    usdt_transferred: Decimal
    receive_amount: Decimal
    fx_rate: Decimal

    def as_dict(self):
        d = asdict(self)
        return {k: (str(v) if isinstance(v, Decimal) else v) for k, v in d.items()}


def _cheapest_network():
    oracle = registry.network_fee_oracle()
    networks = settings.UBIQUE["SUPPORTED_NETWORKS"]
    return min(((n, oracle.fee_usdt(n)) for n in networks), key=lambda x: x[1])


def build_quote(*, send_amount, send_currency, receive_currency) -> Quote:
    cfg = settings.UBIQUE
    send_amount = Decimal(str(send_amount))

    lo, hi = Decimal(str(cfg["MIN_SEND"])), Decimal(str(cfg["MAX_SEND"]))
    if not (lo <= send_amount <= hi):
        raise ValueError(f"Amount must be between {lo} and {hi} {send_currency}.")

    fx = registry.fx_oracle()

    # 1) Card -> USDT (on-ramp fee taken by the acquiring provider, ~2%).
    onramp_fee_rate = Decimal("0.02")
    onramp_fee = send_amount * onramp_fee_rate
    send_in_usdt = (send_amount - onramp_fee) * fx.rate(send_currency, "USDT")

    # 2) Cheapest on-chain network.
    network, network_fee = _cheapest_network()

    # 3) Ubique commission + a flat-ish payout fee (1% here).
    commission = send_amount * Decimal(str(cfg["COMMISSION_RATE"]))
    commission_usdt = commission * fx.rate(send_currency, "USDT")
    payout_fee_usdt = send_in_usdt * Decimal("0.01")

    usdt_after = send_in_usdt - network_fee - commission_usdt - payout_fee_usdt
    if usdt_after <= 0:
        raise ValueError("Amount too small to cover fees.")

    # 4) USDT -> recipient currency at mid + spread.
    spread = Decimal("1") - Decimal(str(cfg["FX_SPREAD"]))
    receive_amount = usdt_after * fx.rate("USDT", receive_currency) * spread
    # Effective send->receive rate, crossed via USDT so we don't need every pair.
    fx_rate = fx.rate(send_currency, "USDT") * fx.rate("USDT", receive_currency)

    return Quote(
        send_amount=money(send_amount),
        send_currency=send_currency,
        receive_currency=receive_currency,
        onramp_fee=money(onramp_fee),
        network=network,
        network_fee_usdt=usdt(network_fee),
        payout_fee=usdt(payout_fee_usdt),
        commission=money(commission),
        usdt_transferred=usdt(usdt_after),
        receive_amount=money(receive_amount),
        fx_rate=fx_rate,
    )
