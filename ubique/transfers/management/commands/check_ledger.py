"""Print the trial balance and flag ledger anomalies.

    python manage.py check_ledger

Exits non-zero if any integrity anomaly is found (suitable for monitoring).
"""

from django.core.management.base import BaseCommand

from ubique.transfers.ledger import balances, completed_without_payout


class Command(BaseCommand):
    help = "Trial balance + integrity checks for the ledger."

    def handle(self, *args, **options):
        self.stdout.write("Trial balance (net credits − debits):")
        for (account, currency), amount in sorted(balances().items()):
            self.stdout.write(f"  {account:<18} {amount:>16} {currency}")

        anomalies = completed_without_payout()
        if anomalies:
            self.stderr.write(self.style.ERROR(
                f"ANOMALY: completed transfers without payout entries: {anomalies}"
            ))
            raise SystemExit(1)
        self.stdout.write(self.style.SUCCESS("Ledger integrity OK."))
