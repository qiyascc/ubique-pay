"""Outbound webhooks — signed, retried event delivery to integrations.

Events are enqueued as OutboundDelivery rows and pushed by
``manage.py deliver_webhooks``. Each request carries::

    X-Ubique-Timestamp: <unix seconds>
    X-Ubique-Signature: hex HMAC-SHA256(secret, f"{timestamp}.{body}")

so receivers can verify authenticity and reject replays outside a ±5-minute
window. Failed deliveries back off exponentially and are dead-lettered after
``OUTBOUND_WEBHOOK_MAX_ATTEMPTS``.
"""

import hashlib
import hmac
import json
import time
import urllib.request
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from .models import OutboundDelivery, WebhookEndpoint


def sign(secret: str, timestamp: str, body: str) -> str:
    return hmac.new(secret.encode(), f"{timestamp}.{body}".encode(), hashlib.sha256).hexdigest()


def enqueue(event_type: str, payload: dict):
    """Queue a delivery of ``event_type`` to every subscribed, enabled endpoint."""
    for endpoint in WebhookEndpoint.objects.filter(enabled=True):
        if endpoint.subscribes(event_type):
            OutboundDelivery.objects.create(
                endpoint=endpoint, event_type=event_type, payload=payload
            )


def send_request(url: str, body: str, headers: dict, timeout: int = 10) -> int:
    """POST the signed body; return the HTTP status. Overridable in tests."""
    req = urllib.request.Request(url, data=body.encode(), headers=headers, method="POST")
    # url is an operator-configured integration endpoint.
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosec B310
        return resp.status


def _schedule_retry(delivery, max_attempts, error=""):
    if delivery.attempts >= max_attempts:
        delivery.status = OutboundDelivery.Status.FAILED
    else:
        backoff = min(2 ** delivery.attempts, 3600)
        delivery.next_attempt_at = timezone.now() + timedelta(seconds=backoff)
    delivery.error = str(error)[:500]


def deliver_due(now=None):
    """Send all due pending deliveries. Returns (delivered, failed) counts."""
    now = now or timezone.now()
    max_attempts = settings.UBIQUE["OUTBOUND_WEBHOOK_MAX_ATTEMPTS"]
    delivered = failed = 0
    due = OutboundDelivery.objects.filter(
        status=OutboundDelivery.Status.PENDING, next_attempt_at__lte=now
    ).select_related("endpoint")
    for delivery in due:
        body = json.dumps({
            "id": delivery.id, "event": delivery.event_type, "data": delivery.payload,
        }, separators=(",", ":"))
        ts = str(int(time.time()))
        headers = {
            "Content-Type": "application/json",
            "X-Ubique-Timestamp": ts,
            "X-Ubique-Signature": sign(delivery.endpoint.secret, ts, body),
        }
        delivery.attempts += 1
        try:
            code = send_request(delivery.endpoint.url, body, headers)
            delivery.response_code = code
            if 200 <= code < 300:
                delivery.status = OutboundDelivery.Status.DELIVERED
                delivery.error = ""
                delivered += 1
            else:
                _schedule_retry(delivery, max_attempts, f"HTTP {code}")
        except Exception as exc:  # noqa: BLE001 - retry on any transport error
            _schedule_retry(delivery, max_attempts, exc)
        if delivery.status == OutboundDelivery.Status.FAILED:
            failed += 1
        delivery.save()
    return delivered, failed
