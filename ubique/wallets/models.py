from django.conf import settings
from django.db import models


class PaymentCard(models.Model):
    """A tokenized card. The PAN never touches our database (PCI): we keep only
    the provider's token and the last four digits for display."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="cards"
    )
    provider_token = models.CharField(max_length=255)
    brand = models.CharField(max_length=20, blank=True)
    last4 = models.CharField(max_length=4)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.brand} ****{self.last4}"


class Recipient(models.Model):
    """A saved payout destination: a tokenized card belonging to someone the
    user sends money to. The PAN is never stored — only the token + last 4."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="recipients"
    )
    name = models.CharField(max_length=128)
    card_token = models.CharField(max_length=255)
    brand = models.CharField(max_length=20, blank=True)
    last4 = models.CharField(max_length=4)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} · {self.brand} ····{self.last4}"


class CryptoAccount(models.Model):
    """A user's own crypto destination (e.g. their TON USDT address)."""

    NETWORKS = [("TON", "TON"), ("SOLANA", "Solana"), ("TRON", "TRON")]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="crypto_accounts"
    )
    network = models.CharField(max_length=10, choices=NETWORKS, default="TON")
    address = models.CharField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("user", "network", "address")

    def __str__(self):
        return f"{self.network}:{self.address[:8]}…"
