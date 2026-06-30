import hashlib
import hmac
import json
from decimal import Decimal

from django.conf import settings as dj_settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings

from ubique.transfers import service
from ubique.transfers.models import LedgerEntry, Transfer
from ubique.transfers.state import Status
from ubique.wallets.models import PaymentCard

User = get_user_model()
SECRET = "whook-secret"


def ubique(**over):
    return {**dj_settings.UBIQUE, **over}


def sign(secret, body: bytes) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


class _Base(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(phone="+994500000123")
        self.user.kyc_status = "verified"
        self.user.save()
        self.card = PaymentCard.objects.create(
            user=self.user, provider_token="tok", brand="Visa", last4="1436"
        )

    def _create(self, key="k", amount="200", last4="9999"):
        return service.create_transfer(
            user=self.user, source_card=self.card, recipient_card_last4=last4,
            recipient_reference="J", send_amount=Decimal(amount),
            send_currency="USD", receive_currency="AZN", idempotency_key=key,
        )

    def _pending_payin(self, key="k", ref="pref1"):
        t = self._create(key=key)
        t.advance(Status.PAYIN_PENDING)
        t.payin_ref = ref
        t.save()
        return t


class WebhookTests(_Base):
    def _post(self, body, sig):
        return self.client.post(
            "/api/v1/transfers/webhooks/onramp/", data=body,
            content_type="application/json", HTTP_X_UBIQUE_SIGNATURE=sig,
        )

    def test_signed_webhook_completes_transfer(self):
        t = self._pending_payin()
        body = json.dumps({"id": "e1", "type": "payin.settled", "ref": "pref1"}).encode()
        with override_settings(UBIQUE=ubique(ONRAMP_WEBHOOK_SECRET=SECRET)):
            r = self._post(body, sign(SECRET, body))
        self.assertEqual(r.status_code, 200)
        t.refresh_from_db()
        self.assertEqual(t.status, Status.COMPLETED)

    def test_bad_signature_rejected(self):
        t = self._pending_payin()
        body = json.dumps({"id": "e2", "type": "payin.settled", "ref": "pref1"}).encode()
        with override_settings(UBIQUE=ubique(ONRAMP_WEBHOOK_SECRET=SECRET)):
            r = self._post(body, "deadbeef")
        self.assertEqual(r.status_code, 401)
        t.refresh_from_db()
        self.assertEqual(t.status, Status.PAYIN_PENDING)

    def test_duplicate_event_does_not_double_process(self):
        t = self._pending_payin()
        body = json.dumps({"id": "dup", "type": "payin.settled", "ref": "pref1"}).encode()
        sig = sign(SECRET, body)
        with override_settings(UBIQUE=ubique(ONRAMP_WEBHOOK_SECRET=SECRET)):
            self._post(body, sig)
            count = LedgerEntry.objects.count()
            self._post(body, sig)  # replay
        self.assertEqual(LedgerEntry.objects.count(), count)


class RiskTests(_Base):
    def test_velocity_limit(self):
        with override_settings(UBIQUE=ubique(MAX_DAILY=100)):
            self._create(key="a", amount="80")
            with self.assertRaises(service.LimitExceeded):
                self._create(key="b", amount="80")

    def test_compliance_denylist(self):
        with override_settings(UBIQUE=ubique(DENYLIST=["9999"])):
            with self.assertRaises(service.ComplianceReject):
                self._create(key="c", last4="9999")


class ReconcileTests(_Base):
    def test_reconcile_settles_pending_payin(self):
        # Mock on-ramp get_payin reports "settled" → reconciliation completes it.
        t = self._pending_payin(ref="pref-recon")
        call_command("reconcile_transfers")
        t.refresh_from_db()
        self.assertEqual(t.status, Status.COMPLETED)


class CorridorTests(_Base):
    def test_unknown_corridor_is_rejected(self):
        from ubique.quotes.engine import build_quote
        with self.assertRaises(ValueError):
            build_quote(send_amount=Decimal("200"), send_currency="USD", receive_currency="XYZ")

    def test_disabled_corridor_is_rejected(self):
        from ubique.corridors.models import Corridor
        from ubique.quotes.engine import build_quote
        Corridor.objects.filter(send_currency="USD", receive_currency="AZN").update(enabled=False)
        with self.assertRaises(ValueError):
            build_quote(send_amount=Decimal("200"), send_currency="USD", receive_currency="AZN")

    def test_corridor_restricts_network(self):
        from ubique.corridors.models import Corridor
        from ubique.quotes.engine import build_quote
        # Force this corridor onto TRON even though TON is cheaper globally.
        Corridor.objects.filter(send_currency="USD", receive_currency="AZN").update(networks="TRON")
        q = build_quote(send_amount=Decimal("200"), send_currency="USD", receive_currency="AZN")
        self.assertEqual(q.network, "TRON")


class LiquidityTests(_Base):
    def test_insufficient_float_blocks_transfer(self):
        with override_settings(UBIQUE=ubique(LIQUIDITY_ENFORCED=True)):
            t = self._create(key="liq1")
            with self.assertRaises(service.LiquidityError):
                service.execute(t.id)
            t.refresh_from_db()
            self.assertEqual(t.status, Status.QUOTED)

    def test_sufficient_float_completes_and_debits(self):
        from ubique.corridors.models import TreasuryBalance
        TreasuryBalance.objects.create(currency="AZN", available=Decimal("1000"))
        with override_settings(UBIQUE=ubique(LIQUIDITY_ENFORCED=True)):
            t = self._create(key="liq2")
            service.execute(t.id)
            t.refresh_from_db()
            self.assertEqual(t.status, Status.COMPLETED)
            bal = TreasuryBalance.objects.get(currency="AZN")
            self.assertEqual(bal.available, Decimal("1000") - t.receive_amount)
