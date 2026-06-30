"""Stubs for the real provider adapters.

These document exactly where each researched integration plugs in. They raise
NotImplementedError until wired with real credentials, so they can be selected
via settings without pretending to move money.
"""

from decimal import Decimal

from .base import ChainResult, ChainSender, OnRampProvider, PayoutProvider


class TransakOnRampProvider(OnRampProvider):
    """Card -> USDT via Transak's Whitelabel/Orders API.

    Flow: POST create-order (fiat amount, USDT, destination = treasury wallet),
    sender pays by card, Transak settles USDT on-chain. Poll/webhook for status.
    Docs: https://docs.transak.com/  (Banxa is a drop-in alternative.)
    """

    def create_payin(self, *, amount, currency, card_token, idempotency_key):
        raise NotImplementedError("Wire Transak/Banxa Orders API + webhook here.")

    def get_payin(self, provider_ref):
        raise NotImplementedError


class TonChainSender(ChainSender):
    """USDT-TON jetton transfer via the `tonutils` library.

    USDT-TON uses 6 decimals; gas is ~0.05 TON per transfer (paid in TON). A
    fresh recipient needs its jetton-wallet contract deployed (a few cents of
    TON), funded by the forward amount. See tonutils examples/jetton/transfer.
    """

    def send(self, *, network, to_address, usdt_amount, idempotency_key) -> ChainResult:
        raise NotImplementedError(
            "Implement with tonutils: ToncenterV3Client + WalletV4R2 + "
            "JettonWalletStandard.transfer (amount * 10**6)."
        )

    def get_status(self, tx_hash, network):
        raise NotImplementedError


class VisaDirectPayoutProvider(PayoutProvider):
    """Push-to-card payout via Visa Direct (OCT) or Mastercard Send.

    Submit an Original Credit Transaction to credit the recipient's card.
    Aggregators (TabaPay, Checkout.com, Cross River) expose a single API over
    both networks. Off-ramp providers (Banxa) are the crypto-native alternative.
    """

    def create_payout(self, *, amount, currency, destination_card, idempotency_key):
        raise NotImplementedError("Wire Visa Direct OCT / Mastercard Send here.")

    def get_payout(self, provider_ref):
        raise NotImplementedError
