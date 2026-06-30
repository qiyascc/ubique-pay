from decimal import Decimal

from django.db import models


class Corridor(models.Model):
    """A supported send→receive currency pair, with limits, allowed networks
    and an optional commission override. Disabled corridors are rejected at
    quote time."""

    send_currency = models.CharField(max_length=8)
    receive_currency = models.CharField(max_length=8)
    # Comma-separated networks this corridor may settle over (subset of the
    # global SUPPORTED_NETWORKS); the router still picks the cheapest.
    networks = models.CharField(max_length=64, default="TON,TRON")
    min_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("20"))
    max_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("10000"))
    commission_rate = models.DecimalField(
        max_digits=5, decimal_places=4, null=True, blank=True,
        help_text="Overrides the global commission when set.",
    )
    enabled = models.BooleanField(default=True)

    class Meta:
        unique_together = ("send_currency", "receive_currency")
        ordering = ["send_currency", "receive_currency"]

    def __str__(self):
        flag = "" if self.enabled else " (disabled)"
        return f"{self.send_currency}→{self.receive_currency}{flag}"

    def network_list(self):
        return [n.strip().upper() for n in self.networks.split(",") if n.strip()]


class TreasuryBalance(models.Model):
    """Fiat payout float per currency. When liquidity enforcement is on, a
    payout is blocked unless its currency has enough available float."""

    currency = models.CharField(max_length=8, unique=True)
    available = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0"))
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["currency"]

    def __str__(self):
        return f"{self.currency}: {self.available}"
