"""Provider adapter interfaces.

Every external money-moving dependency sits behind one of these so the core
transfer logic stays testable and providers can be swapped per corridor by
pointing the ``UBIQUE[...]`` settings at a different dotted path.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal


@dataclass
class PayinResult:
    provider_ref: str
    status: str  # "pending" | "settled" | "failed"
    usdt_amount: Decimal


@dataclass
class ChainResult:
    tx_hash: str
    status: str  # "pending" | "confirmed" | "failed"
    network: str


@dataclass
class PayoutResult:
    provider_ref: str
    status: str  # "pending" | "paid" | "failed"


class OnRampProvider(ABC):
    """Charges the sender's card and settles USDT to our treasury wallet."""

    @abstractmethod
    def create_payin(self, *, amount: Decimal, currency: str, card_token: str,
                     idempotency_key: str) -> PayinResult: ...

    @abstractmethod
    def get_payin(self, provider_ref: str) -> PayinResult: ...


class ChainSender(ABC):
    """Sends USDT on a specific network."""

    @abstractmethod
    def send(self, *, network: str, to_address: str, usdt_amount: Decimal,
             idempotency_key: str) -> ChainResult: ...

    @abstractmethod
    def get_status(self, tx_hash: str, network: str) -> ChainResult: ...


class PayoutProvider(ABC):
    """Pays out to the recipient's bank card in their local currency."""

    @abstractmethod
    def create_payout(self, *, amount: Decimal, currency: str,
                      destination_card: str, idempotency_key: str) -> PayoutResult: ...

    @abstractmethod
    def get_payout(self, provider_ref: str) -> PayoutResult: ...


class FxOracle(ABC):
    @abstractmethod
    def rate(self, base: str, quote: str) -> Decimal:
        """Mid-market price of 1 unit of ``base`` in ``quote``."""


class NetworkFeeOracle(ABC):
    @abstractmethod
    def fee_usdt(self, network: str) -> Decimal:
        """Estimated cost (in USDT) of one USDT transfer on ``network``."""
