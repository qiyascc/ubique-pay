"""Ledger reporting & integrity checks.

The per-transfer double-entry rows let us reconstruct a trial balance (net per
account per currency) and assert basic money-movement invariants.
"""

from collections import defaultdict
from decimal import Decimal

from django.db.models import Sum

from .models import LedgerEntry, Transfer
from .state import Status


def balances():
    """Net balance (credits − debits) per (account, currency)."""
    bal = defaultdict(lambda: Decimal("0"))
    rows = (
        LedgerEntry.objects.values("account", "currency", "direction")
        .annotate(total=Sum("amount"))
    )
    for row in rows:
        sign = Decimal("1") if row["direction"] == "credit" else Decimal("-1")
        bal[(row["account"], row["currency"])] += sign * row["total"]
    return dict(bal)


def usdt_is_conserved():
    """USDT must never be created or destroyed: every credit to a USDT pool is
    matched by a debit somewhere. Returns the residual (0 means balanced)."""
    usdt = {k: v for k, v in balances().items() if k[1] == "USDT"}
    # treasury_usdt + payout_pool should net to the USDT we still hold; the sum
    # of all USDT debits and credits across pools must be conserved.
    return sum(usdt.values(), Decimal("0"))


def completed_without_payout():
    """COMPLETED transfers missing the recipient payout entry (an anomaly)."""
    anomalies = []
    for transfer in Transfer.objects.filter(status=Status.COMPLETED):
        if not transfer.ledger_entries.filter(
            account="recipient_card", direction="credit"
        ).exists():
            anomalies.append(transfer.id)
    return anomalies
