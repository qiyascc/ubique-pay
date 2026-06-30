"""Real provider adapters.

These contain the actual integration code; they are credential-gated (read from
the environment) and selected via the ``UBIQUE_*`` settings. The mock providers
remain the default so the project runs without external accounts.
"""

import os
from decimal import Decimal

from django.core.exceptions import ImproperlyConfigured

from .base import (
    ChainResult,
    ChainSender,
    OnRampProvider,
    PayinResult,
    PayoutProvider,
    PayoutResult,
)

# USDT jetton master on TON mainnet, 6 decimals.
USDT_TON_MASTER = "EQCxE6mUtQJKFnGfaROTKOt1lZbDiiX1kCixRv7Nw2Id_sDs"
USDT_DECIMALS = 6


class TransakOnRampProvider(OnRampProvider):
    """Card → USDT via Transak's Orders API.

    Env: TRANSAK_API_KEY, TRANSAK_ENV (STAGING|PRODUCTION),
         UBIQUE_TREASURY_WALLET (USDT-TON address that receives settlement).
    """

    def __init__(self):
        self.api_key = os.environ.get("TRANSAK_API_KEY", "")
        self.wallet = os.environ.get("UBIQUE_TREASURY_WALLET", "")
        env = os.environ.get("TRANSAK_ENV", "STAGING").upper()
        self.base = (
            "https://api.transak.com" if env == "PRODUCTION"
            else "https://api-stg.transak.com"
        )
        if not self.api_key or not self.wallet:
            raise ImproperlyConfigured(
                "TransakOnRampProvider needs TRANSAK_API_KEY and "
                "UBIQUE_TREASURY_WALLET."
            )

    def create_payin(self, *, amount, currency, card_token, idempotency_key):
        import json
        import urllib.request

        payload = json.dumps({
            "fiatCurrency": currency,
            "fiatAmount": float(amount),
            "cryptoCurrency": "USDT",
            "network": "ton",
            "walletAddress": self.wallet,
            "paymentMethod": "credit_debit_card",
            "partnerOrderId": idempotency_key,
        }).encode()
        req = urllib.request.Request(
            f"{self.base}/api/v2/orders",
            data=payload,
            headers={"Content-Type": "application/json", "api-secret": self.api_key},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode())
        order = data.get("response", data)
        return PayinResult(
            provider_ref=str(order.get("id", idempotency_key)),
            status="pending",
            usdt_amount=Decimal(str(order.get("cryptoAmount", "0"))),
        )

    def get_payin(self, provider_ref):
        raise NotImplementedError("Poll Transak order status or use webhooks.")


class TonChainSender(ChainSender):
    """USDT-TON jetton transfer via the `tonutils` library.

    Env: TON_MNEMONIC (24 words, space-separated) for the treasury wallet,
         TON_API_KEY (toncenter). USDT uses 6 decimals; gas ~0.05 TON is paid
         from the wallet's TON balance; a fresh recipient's jetton wallet is
         deployed automatically on first transfer.
    """

    def __init__(self):
        self.mnemonic = os.environ.get("TON_MNEMONIC", "")
        self.api_key = os.environ.get("TON_API_KEY", "")
        self.is_testnet = os.environ.get("TON_TESTNET", "0") == "1"
        if not self.mnemonic:
            raise ImproperlyConfigured("TonChainSender needs TON_MNEMONIC.")

    @staticmethod
    def to_jetton_units(usdt_amount) -> int:
        """USDT decimal amount → integer jetton units (6 decimals)."""
        return int(Decimal(str(usdt_amount)) * (10 ** USDT_DECIMALS))

    def send(self, *, network, to_address, usdt_amount, idempotency_key) -> ChainResult:
        if network.upper() != "TON":
            raise NotImplementedError(f"TonChainSender only handles TON, not {network}.")

        import asyncio

        from tonutils.client import ToncenterV3Client
        from tonutils.jetton import JettonWalletStablecoin
        from tonutils.utils import to_nano
        from tonutils.wallet import WalletV4R2

        async def _run():
            client = ToncenterV3Client(api_key=self.api_key, is_testnet=self.is_testnet)
            wallet, _, _, _ = WalletV4R2.from_mnemonic(client, self.mnemonic.split())
            body = JettonWalletStablecoin.build_transfer_body(
                jetton_amount=self.to_jetton_units(usdt_amount),
                recipient_address=to_address,
                response_address=wallet.address,
            )
            jetton_wallet = await JettonWalletStablecoin.get_wallet_address(
                client, wallet.address, USDT_TON_MASTER
            )
            return await wallet.transfer(
                destination=jetton_wallet,
                amount=to_nano(0.05),  # TON for gas + jetton-wallet deploy
                body=body,
            )

        tx_hash = asyncio.run(_run())
        return ChainResult(tx_hash=str(tx_hash), status="pending", network="TON")

    def get_status(self, tx_hash, network):
        raise NotImplementedError("Poll toncenter for the transaction status.")


class VisaDirectPayoutProvider(PayoutProvider):
    """Push-to-card payout via Visa Direct (OCT) or Mastercard Send.

    Visa Direct uses mutual-TLS + request signing and merchant onboarding, so
    this is left as a documented integration point. Aggregators (TabaPay,
    Checkout.com, Cross River) expose a single REST API over both card networks
    and are the fastest way to ship a real payout leg.
    """

    def create_payout(self, *, amount, currency, destination_card, idempotency_key):
        raise NotImplementedError(
            "Wire Visa Direct OCT / Mastercard Send (or an aggregator) here."
        )

    def get_payout(self, provider_ref):
        raise NotImplementedError


class CheckoutPayoutProvider(PayoutProvider):
    """Push-to-card payout via Checkout.com (an aggregator over Visa/Mastercard).

    Env: CHECKOUT_SECRET_KEY, CHECKOUT_ENV (sandbox|production),
         CHECKOUT_SOURCE_ID (your funding currency-account id).
    ``destination_card`` is the recipient card token from Checkout's card vault
    (never a raw PAN).
    """

    def __init__(self):
        self.secret = os.environ.get("CHECKOUT_SECRET_KEY", "")
        self.source_id = os.environ.get("CHECKOUT_SOURCE_ID", "")
        env = os.environ.get("CHECKOUT_ENV", "sandbox").lower()
        self.base = (
            "https://api.checkout.com" if env == "production"
            else "https://api.sandbox.checkout.com"
        )
        if not self.secret or not self.source_id:
            raise ImproperlyConfigured(
                "CheckoutPayoutProvider needs CHECKOUT_SECRET_KEY and "
                "CHECKOUT_SOURCE_ID."
            )

    def create_payout(self, *, amount, currency, destination_card, idempotency_key):
        import json
        import urllib.request

        payload = json.dumps({
            "source": {"type": "currency_account", "id": self.source_id},
            "destination": {"type": "id", "id": destination_card},
            "amount": int(Decimal(str(amount)) * 100),  # minor units
            "currency": currency,
            "reference": idempotency_key,
            "instruction": {"purpose": "remittance"},
        }).encode()
        req = urllib.request.Request(
            f"{self.base}/payments",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.secret}",
                "Cko-Idempotency-Key": idempotency_key,
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode())
        return PayoutResult(
            provider_ref=str(data.get("id", idempotency_key)),
            status="pending",  # confirmed later by webhook
        )

    def get_payout(self, provider_ref):
        raise NotImplementedError("Poll Checkout.com payment status or use webhooks.")
