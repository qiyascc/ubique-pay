"""Deliver due outbound webhook events (run on a short timer)."""

from django.core.management.base import BaseCommand

from ubique.transfers.outbound import deliver_due


class Command(BaseCommand):
    help = "Send pending outbound webhook deliveries with retry/backoff."

    def handle(self, *args, **options):
        delivered, failed = deliver_due()
        self.stdout.write(self.style.SUCCESS(
            f"Outbound webhooks: {delivered} delivered, {failed} dead-lettered."
        ))
