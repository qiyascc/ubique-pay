"""Signed, idempotent provider webhooks with a retry / dead-letter queue.

Each request must carry ``X-Ubique-Signature`` = hex HMAC-SHA256 of the raw body
using the per-provider secret. Events are deduped on (provider, external_id).

Processing is resilient: if it can't complete yet (e.g. the webhook arrives
before the transfer row is committed) a ``RetryableError`` is raised, the event
is kept unprocessed with the error recorded, and ``manage.py retry_webhooks``
re-runs it. Events that exceed ``MAX_WEBHOOK_ATTEMPTS`` are dead-lettered
(visible in the admin).
"""

import hashlib
import hmac
import json
import time

from django.conf import settings
from django.db import transaction
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from . import service
from .models import Transfer, WebhookEvent


class RetryableError(Exception):
    pass


# provider -> (transfer ref field, {event type: action})
_HANDLERS = {
    "onramp": ("payin_ref", {"payin.settled": "settle", "payin.failed": "fail"}),
    "payout": ("payout_ref", {"payout.paid": "complete", "payout.failed": "fail"}),
}


def verify_signature(secret: str, raw_body: bytes, signature: str,
                     timestamp: str = None, window: int = 300) -> bool:
    """Verify the HMAC-SHA256 signature. When a timestamp is supplied the signed
    message is ``"<timestamp>.<body>"`` and the timestamp must be within
    ``window`` seconds (replay protection); otherwise the raw body is signed
    (legacy)."""
    if not secret or not signature:
        return False
    if timestamp:
        try:
            ts = int(timestamp)
        except (TypeError, ValueError):
            return False
        if abs(time.time() - ts) > window:
            return False
        message = f"{ts}.".encode() + raw_body
    else:
        message = raw_body
    expected = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def process_event(event: WebhookEvent):
    """Apply one event to its transfer. Raises RetryableError if not yet possible."""
    cfg = _HANDLERS.get(event.provider)
    if not cfg:
        return
    ref_field, actions = cfg
    action = actions.get(event.event_type)
    ref = (event.payload or {}).get("ref")
    if not action or not ref:
        return  # unknown/irrelevant event — nothing to do

    transfer = Transfer.objects.select_for_update().filter(**{ref_field: ref}).first()
    if transfer is None:
        raise RetryableError(f"No transfer for {ref_field}={ref} yet.")

    if action == "settle":
        service.settle_payin(transfer)
    elif action == "complete":
        service.complete_payout(transfer)
    elif action == "fail":
        service.fail_and_refund(transfer, "Provider reported failure.")


def _run(event):
    """Attempt processing, recording attempts/errors. Returns True if processed."""
    event.attempts += 1
    try:
        process_event(event)
        event.processed = True
        event.error = ""
    except RetryableError as exc:
        event.error = str(exc)
    except Exception as exc:  # noqa: BLE001 - keep for retry, record the reason
        event.error = f"{type(exc).__name__}: {exc}"
    event.save(update_fields=["processed", "attempts", "error"])
    return event.processed


class _BaseWebhook(APIView):
    authentication_classes: list = []
    permission_classes = [AllowAny]
    provider = ""
    secret_setting = ""

    def post(self, request):
        secret = settings.UBIQUE.get(self.secret_setting, "")
        signature = request.headers.get("X-Ubique-Signature", "")
        timestamp = request.headers.get("X-Ubique-Timestamp")
        window = settings.UBIQUE["WEBHOOK_REPLAY_WINDOW"]
        if not verify_signature(secret, request.body, signature, timestamp, window):
            return Response({"detail": "Invalid signature."},
                            status=status.HTTP_401_UNAUTHORIZED)
        try:
            data = json.loads(request.body.decode())
            event_id = data["id"]
        except (ValueError, KeyError):
            return Response({"detail": "Malformed event."},
                            status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            event, created = WebhookEvent.objects.select_for_update().get_or_create(
                provider=self.provider, external_id=event_id,
                defaults={"event_type": data.get("type", ""), "payload": data},
            )
            if not created and event.processed:
                return Response({"detail": "Already processed."})  # idempotent
            _run(event)
        return Response({"detail": "ok"})


class OnRampWebhook(_BaseWebhook):
    provider = "onramp"
    secret_setting = "ONRAMP_WEBHOOK_SECRET"


class PayoutWebhook(_BaseWebhook):
    provider = "payout"
    secret_setting = "PAYOUT_WEBHOOK_SECRET"
