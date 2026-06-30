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
        self._pending_payin()
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
        with override_settings(UBIQUE=ubique(DENYLIST=["9999"])), \
                self.assertRaises(service.ComplianceReject):
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


class WebhookRetryTests(_Base):
    def _post_onramp(self, body):
        with override_settings(UBIQUE=ubique(ONRAMP_WEBHOOK_SECRET=SECRET)):
            return self.client.post(
                "/api/v1/transfers/webhooks/onramp/", data=body,
                content_type="application/json", HTTP_X_UBIQUE_SIGNATURE=sign(SECRET, body),
            )

    def test_event_before_transfer_is_retried(self):
        from ubique.transfers.models import WebhookEvent
        body = json.dumps({"id": "early", "type": "payin.settled", "ref": "late-ref"}).encode()
        r = self._post_onramp(body)
        self.assertEqual(r.status_code, 200)
        ev = WebhookEvent.objects.get(external_id="early")
        self.assertFalse(ev.processed)
        self.assertEqual(ev.attempts, 1)

        # The transfer shows up later; the retry queue then completes it.
        t = self._pending_payin(key="late", ref="late-ref")
        with override_settings(UBIQUE=ubique(ONRAMP_WEBHOOK_SECRET=SECRET)):
            call_command("retry_webhooks")
        ev.refresh_from_db()
        t.refresh_from_db()
        self.assertTrue(ev.processed)
        self.assertEqual(t.status, Status.COMPLETED)

    def test_dead_letter_after_max_attempts(self):
        from ubique.transfers.models import WebhookEvent
        body = json.dumps({"id": "dead", "type": "payin.settled", "ref": "never"}).encode()
        with override_settings(UBIQUE=ubique(ONRAMP_WEBHOOK_SECRET=SECRET, MAX_WEBHOOK_ATTEMPTS=2)):
            self._post_onramp(body)        # attempt 1
            call_command("retry_webhooks")  # attempt 2 → at the limit
        ev = WebhookEvent.objects.get(external_id="dead")
        self.assertFalse(ev.processed)
        self.assertTrue(ev.is_dead_lettered(2))


class FxOracleTests(TestCase):
    def test_median_of_sources_and_caches(self):
        from django.core.cache import cache

        from ubique.providers.fx import CachingMultiSourceFxOracle
        cache.delete("fx:USDT:AZN")
        oracle = CachingMultiSourceFxOracle()
        # SourceA=1.70*1.002, SourceB=1.70*0.998 → median = 1.70
        self.assertEqual(oracle.rate("USDT", "AZN"), Decimal("1.70"))
        self.assertIsNotNone(cache.get("fx:USDT:AZN"))  # result cached

    def test_same_currency_is_one(self):
        from ubique.providers.fx import CachingMultiSourceFxOracle
        self.assertEqual(CachingMultiSourceFxOracle().rate("USD", "USD"), Decimal("1"))


class DynamicPricingTests(_Base):
    def _quote(self, amount):
        from ubique.quotes.engine import build_quote
        return build_quote(send_amount=Decimal(amount), send_currency="USD", receive_currency="AZN")

    def test_corridor_onramp_fee_override(self):
        from ubique.corridors.models import Corridor
        base = self._quote("200")
        Corridor.objects.filter(send_currency="USD", receive_currency="AZN").update(
            onramp_fee_rate=Decimal("0.05")
        )
        higher = self._quote("200")
        self.assertEqual(higher.onramp_fee, Decimal("10.00"))   # 200 * 0.05
        self.assertGreater(base.receive_amount, higher.receive_amount)

    def test_amount_tier_lowers_commission(self):
        from ubique.corridors.models import Corridor
        Corridor.objects.filter(send_currency="USD", receive_currency="AZN").update(
            commission_rate=Decimal("0.02"),
            tier_threshold=Decimal("500"), tier_commission_rate=Decimal("0.005"),
        )
        self.assertEqual(self._quote("200").commission, Decimal("4.00"))   # 200 * 2%
        self.assertEqual(self._quote("600").commission, Decimal("3.00"))   # 600 * 0.5% (tier)


class OutboundWebhookTests(_Base):
    def test_completed_enqueues_and_delivers_signed(self):
        from unittest import mock

        from ubique.transfers import outbound
        from ubique.transfers.models import OutboundDelivery, WebhookEndpoint

        WebhookEndpoint.objects.create(
            url="https://merchant.example/hook", secret="whsec", events="*")
        t = self._create(key="ob1")
        service.execute(t.id)  # completes → enqueues a delivery

        delivery = OutboundDelivery.objects.get(event_type="transfer.completed")
        captured = {}

        def fake_send(url, body, headers, timeout=10):
            captured.update(url=url, body=body, headers=headers)
            return 200

        with mock.patch.object(outbound, "send_request", side_effect=fake_send):
            delivered, failed = outbound.deliver_due()

        self.assertEqual(delivered, 1)
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, "delivered")
        # Signature is HMAC-SHA256(secret, "<ts>.<body>").
        ts = captured["headers"]["X-Ubique-Timestamp"]
        self.assertEqual(
            captured["headers"]["X-Ubique-Signature"],
            outbound.sign("whsec", ts, captured["body"]),
        )

    def test_non_2xx_dead_letters_at_limit(self):
        from unittest import mock

        from ubique.transfers import outbound
        from ubique.transfers.models import OutboundDelivery, WebhookEndpoint

        WebhookEndpoint.objects.create(url="https://x/hook", secret="s", events="transfer.completed")
        t = self._create(key="ob2")
        service.execute(t.id)
        with override_settings(UBIQUE=ubique(OUTBOUND_WEBHOOK_MAX_ATTEMPTS=1)), \
                mock.patch.object(outbound, "send_request", return_value=500):
            outbound.deliver_due()
        d = OutboundDelivery.objects.get(event_type="transfer.completed")
        self.assertEqual(d.status, "failed")

    def test_endpoint_event_filter(self):
        from ubique.transfers.models import OutboundDelivery, WebhookEndpoint
        WebhookEndpoint.objects.create(url="https://y/hook", secret="s", events="transfer.refunded")
        t = self._create(key="ob3")
        service.execute(t.id)  # completed, not refunded → nothing queued
        self.assertEqual(OutboundDelivery.objects.count(), 0)


from ubique.common.notify import Notifier  # noqa: E402


class RecordingNotifier(Notifier):
    sent = []

    def send(self, user, event, message):
        RecordingNotifier.sent.append((event, message))


class NotificationTests(_Base):
    def setUp(self):
        super().setUp()
        RecordingNotifier.sent = []

    def test_completed_transfer_notifies_user(self):
        with override_settings(
            UBIQUE=ubique(NOTIFIERS=["ubique.transfers.test_async.RecordingNotifier"])
        ):
            t = self._create(key="nt1")
            service.execute(t.id)
        events = [e for e, _ in RecordingNotifier.sent]
        self.assertIn("transfer.completed", events)


class LedgerIntegrityTests(_Base):
    def test_trial_balance_and_usdt_conservation(self):
        from ubique.transfers.ledger import (
            balances,
            completed_without_payout,
            usdt_is_conserved,
        )
        t = self._create(key="lg1")
        service.execute(t.id)
        bal = balances()
        # USDT nets to zero per pool (in == out); fiat accounts accumulate.
        self.assertEqual(bal.get(("treasury_usdt", "USDT")), Decimal("0"))
        self.assertEqual(bal.get(("payout_pool", "USDT")), Decimal("0"))
        self.assertEqual(usdt_is_conserved(), Decimal("0"))
        self.assertGreater(bal.get(("ubique_revenue", "USD"), Decimal("0")), 0)
        self.assertGreater(bal.get(("recipient_card", "AZN"), Decimal("0")), 0)
        self.assertEqual(completed_without_payout(), [])


class RiskEngineTests(_Base):
    def test_high_amount_is_held_for_review(self):
        t = self._create(key="rk1", amount="1500")
        self.assertEqual(t.risk_decision, "review")
        with self.assertRaises(service.ReviewRequired):
            service.execute(t.id)
        t.refresh_from_db()
        self.assertEqual(t.status, Status.QUOTED)

    def test_release_lets_held_transfer_complete(self):
        t = self._create(key="rk2", amount="1500")
        service.release_for_review(t, self.user)
        service.execute(Transfer.objects.get(pk=t.id).id)
        t.refresh_from_db()
        self.assertEqual(t.status, Status.COMPLETED)

    def test_block_threshold_rejects_creation(self):
        with override_settings(UBIQUE=ubique(RISK_BLOCK_AMOUNT=5000)), \
                self.assertRaises(service.ComplianceReject):
            self._create(key="rk3", amount="6000")

    def test_normal_amount_is_allowed(self):
        t = self._create(key="rk4", amount="200")
        self.assertEqual(t.risk_decision, "allow")


class RefundTests(_Base):
    def _settled_payout_pending(self, key="rf"):
        """Drive a transfer to PAYOUT_PENDING with pay-in settled."""
        t = self._create(key=key)
        t.advance(Status.PAYIN_PENDING)
        t.advance(Status.PAYIN_SETTLED)
        from ubique.transfers.service import _ledger
        _ledger(t, "treasury_usdt", "credit", t.usdt_transferred, "USDT")
        _ledger(t, "ubique_revenue", "credit", t.commission, t.send_currency)
        t.advance(Status.ONCHAIN_SENT)
        t.advance(Status.PAYOUT_PENDING)
        return t

    def test_payout_failure_refunds_sender(self):
        t = self._settled_payout_pending()
        service.fail_and_refund(t, "payout failed")
        t.refresh_from_db()
        self.assertEqual(t.status, Status.REFUNDED)
        self.assertTrue(t.refund_ref)
        # Sender is made whole; commission revenue is reversed to net zero.
        self.assertTrue(t.ledger_entries.filter(account="sender_refund", direction="credit").exists())
        from django.db.models import Sum
        rev = t.ledger_entries.filter(account="ubique_revenue")
        credit = rev.filter(direction="credit").aggregate(s=Sum("amount"))["s"] or 0
        debit = rev.filter(direction="debit").aggregate(s=Sum("amount"))["s"] or 0
        self.assertEqual(credit, debit)

    def test_refund_is_idempotent(self):
        t = self._settled_payout_pending(key="rf2")
        service.fail_and_refund(t, "x")
        t.refresh_from_db()
        service.refund(t)  # second call is a no-op
        t.refresh_from_db()
        self.assertEqual(t.ledger_entries.filter(account="sender_refund").count(), 1)

    def test_no_charge_no_money_refund(self):
        # Failed before pay-in settled → refunded with no money movement.
        t = self._create(key="rf3")
        t.advance(Status.PAYIN_PENDING)
        service.fail_and_refund(t, "payin failed")
        t.refresh_from_db()
        self.assertEqual(t.status, Status.REFUNDED)
        self.assertFalse(t.ledger_entries.filter(account="sender_refund").exists())


class AuditTests(_Base):
    def test_completed_transfer_is_audited(self):
        from ubique.audit.models import AuditLog
        t = self._create(key="aud")
        service.execute(t.id)
        self.assertTrue(AuditLog.objects.filter(
            action="transfer.completed", target=f"transfer:{t.id}").exists())

    def test_refund_is_audited(self):
        from ubique.audit.models import AuditLog
        t = self._create(key="aud2")
        t.advance(Status.PAYIN_PENDING)
        service.fail_and_refund(t, "x")
        self.assertTrue(AuditLog.objects.filter(action="transfer.failed").exists())
        self.assertTrue(AuditLog.objects.filter(action="transfer.refunded").exists())


class MultisigTests(_Base):
    def setUp(self):
        super().setUp()
        self.s1 = User.objects.create_user(phone="+994500000201")
        self.s2 = User.objects.create_user(phone="+994500000202")
        for s in (self.s1, self.s2):
            s.is_treasury_signer = True
            s.save()

    def _settings(self, **over):
        base = {"MULTISIG_ENABLED": True, "MULTISIG_THRESHOLD": 2, "MULTISIG_MIN_USDT": 100}
        base.update(over)
        return override_settings(UBIQUE=ubique(**base))

    def test_large_transfer_awaits_approval(self):
        with self._settings():
            t = self._create(key="ms-a")
            service.execute(t.id)
            t.refresh_from_db()
        self.assertEqual(t.status, Status.APPROVAL_PENDING)
        self.assertEqual(t.onchain_approval.threshold, 2)

    def test_threshold_approvals_complete_it(self):
        with self._settings():
            t = self._create(key="ms-b")
            service.execute(t.id)
            service.approve_onchain(Transfer.objects.get(pk=t.id), self.s1)
            t.refresh_from_db()
            self.assertEqual(t.status, Status.APPROVAL_PENDING)   # 1 of 2
            service.approve_onchain(Transfer.objects.get(pk=t.id), self.s2)
            t.refresh_from_db()
            self.assertEqual(t.status, Status.COMPLETED)          # 2 of 2

    def test_non_signer_cannot_approve(self):
        with self._settings():
            t = self._create(key="ms-c")
            service.execute(t.id)
            with self.assertRaises(service.NotASigner):
                service.approve_onchain(Transfer.objects.get(pk=t.id), self.user)

    def test_below_threshold_skips_approval(self):
        with self._settings(MULTISIG_MIN_USDT=100000):
            t = self._create(key="ms-d")
            service.execute(t.id)
            t.refresh_from_db()
        self.assertEqual(t.status, Status.COMPLETED)


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
