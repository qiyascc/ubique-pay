"""Reconcile in-flight transfers against provider status.

A safety net for missed/late webhooks: polls the on-ramp / payout providers for
transfers stuck in a pending state and advances or fails them. Run on a timer
(cron / systemd timer):

    python manage.py reconcile_transfers
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from ubique.providers import registry
from ubique.transfers import service
from ubique.transfers.models import Transfer
from ubique.transfers.state import Status


class Command(BaseCommand):
    help = "Poll providers and advance stuck transfers."

    def handle(self, *args, **options):
        advanced = 0
        advanced += self._reconcile_payins()
        advanced += self._reconcile_payouts()
        self.stdout.write(self.style.SUCCESS(f"Reconciled {advanced} transfer(s)."))

    def _reconcile_payins(self):
        count = 0
        provider = registry.onramp()
        for tid in Transfer.objects.filter(
            status=Status.PAYIN_PENDING
        ).values_list("id", flat=True):
            with transaction.atomic():
                t = Transfer.objects.select_for_update().get(pk=tid)
                try:
                    res = provider.get_payin(t.payin_ref)
                except NotImplementedError:
                    continue
                if res.status == "settled":
                    service.settle_payin(t)
                    count += 1
                elif res.status == "failed":
                    service.fail(t, "Pay-in failed (reconciliation).")
                    count += 1
        return count

    def _reconcile_payouts(self):
        count = 0
        provider = registry.payout()
        for tid in Transfer.objects.filter(
            status=Status.PAYOUT_PENDING
        ).values_list("id", flat=True):
            with transaction.atomic():
                t = Transfer.objects.select_for_update().get(pk=tid)
                try:
                    res = provider.get_payout(t.payout_ref)
                except NotImplementedError:
                    continue
                if res.status == "paid":
                    service.complete_payout(t)
                    count += 1
                elif res.status == "failed":
                    service.fail(t, "Payout failed (reconciliation).")
                    count += 1
        return count
