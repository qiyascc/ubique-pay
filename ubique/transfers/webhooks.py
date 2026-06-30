"""Signed, idempotent provider webhooks that drive the async state machine.

Each request must carry an ``X-Ubique-Signature`` header = hex HMAC-SHA256 of
the raw body using the per-provider secret. Events are deduped on
(provider, event id) so retries never double-process.

Normalised event body:  {"id": "...", "type": "payin.settled", "ref": "<provider_ref>"}
"""

import hashlib
import hmac
import json

from django.conf import settings
from django.db import transaction
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from . import service
from .models import Transfer, WebhookEvent


def verify_signature(secret: str, raw_body: bytes, signature: str) -> bool:
    if not secret or not signature:
        return False
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


class _BaseWebhook(APIView):
    authentication_classes: list = []
    permission_classes = [AllowAny]
    provider = ""
    secret_setting = ""
    ref_field = ""          # Transfer field that matches event["ref"]
    handlers: dict = {}     # event type -> ("settle"|"complete"|"fail")

    def post(self, request):
        secret = settings.UBIQUE.get(self.secret_setting, "")
        signature = request.headers.get("X-Ubique-Signature", "")
        if not verify_signature(secret, request.body, signature):
            return Response({"detail": "Invalid signature."},
                            status=status.HTTP_401_UNAUTHORIZED)
        try:
            data = json.loads(request.body.decode())
            event_id, etype, ref = data["id"], data["type"], data.get("ref")
        except (ValueError, KeyError):
            return Response({"detail": "Malformed event."},
                            status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            event, created = WebhookEvent.objects.select_for_update().get_or_create(
                provider=self.provider, external_id=event_id,
                defaults={"event_type": etype, "payload": data},
            )
            if not created and event.processed:
                return Response({"detail": "Already processed."})  # idempotent

            action = self.handlers.get(etype)
            if action and ref:
                self._apply(action, ref)
            event.processed = True
            event.save(update_fields=["processed"])
        return Response({"detail": "ok"})

    def _apply(self, action, ref):
        transfer = (
            Transfer.objects.select_for_update()
            .filter(**{self.ref_field: ref}).first()
        )
        if transfer is None:
            return
        if action == "settle":
            service.settle_payin(transfer)
        elif action == "complete":
            service.complete_payout(transfer)
        elif action == "fail":
            service.fail(transfer, "Provider reported failure.")


class OnRampWebhook(_BaseWebhook):
    provider = "onramp"
    secret_setting = "ONRAMP_WEBHOOK_SECRET"
    ref_field = "payin_ref"
    handlers = {"payin.settled": "settle", "payin.failed": "fail"}


class PayoutWebhook(_BaseWebhook):
    provider = "payout"
    secret_setting = "PAYOUT_WEBHOOK_SECRET"
    ref_field = "payout_ref"
    handlers = {"payout.paid": "complete", "payout.failed": "fail"}
