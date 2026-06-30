"""Re-process webhook events that failed transient processing.

Events past MAX_WEBHOOK_ATTEMPTS are left as dead-letters (inspect them in the
admin). Run on a timer next to reconcile_transfers.

    python manage.py retry_webhooks
"""

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from ubique.transfers.models import WebhookEvent
from ubique.transfers.webhooks import _run


class Command(BaseCommand):
    help = "Retry unprocessed webhook events; dead-letter those past the limit."

    def handle(self, *args, **options):
        max_attempts = settings.UBIQUE["MAX_WEBHOOK_ATTEMPTS"]
        processed = dead = 0
        ids = WebhookEvent.objects.filter(
            processed=False, attempts__lt=max_attempts
        ).values_list("id", flat=True)
        for pk in list(ids):
            with transaction.atomic():
                event = WebhookEvent.objects.select_for_update().get(pk=pk)
                if event.processed:
                    continue
                if _run(event):
                    processed += 1
                elif event.attempts >= max_attempts:
                    dead += 1
        self.stdout.write(self.style.SUCCESS(
            f"Retried: {processed} processed, {dead} dead-lettered."
        ))
