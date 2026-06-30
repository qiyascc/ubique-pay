from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from ubique.providers import registry
from ubique.quotes.engine import build_quote
from ubique.transfers import service
from ubique.transfers.state import Status
from ubique.wallets.models import PaymentCard

User = get_user_model()


class QuoteTests(TestCase):
    def test_quote_picks_cheapest_network(self):
        quote = build_quote(send_amount=200, send_currency="USD", receive_currency="AZN")
        oracle = registry.network_fee_oracle()
        cheapest = min(["TON", "SOLANA", "TRON"], key=oracle.fee_usdt)
        self.assertEqual(quote.network, cheapest)
        self.assertGreater(quote.receive_amount, Decimal("0"))

    def test_amount_below_minimum_is_rejected(self):
        with self.assertRaises(ValueError):
            build_quote(send_amount=5, send_currency="USD", receive_currency="AZN")


class TransferServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(phone="+994500000001")
        self.user.kyc_status = "verified"
        self.user.save()
        self.card = PaymentCard.objects.create(
            user=self.user, provider_token="tok_123", brand="Visa", last4="1436"
        )

    def _create(self, key="idem-1"):
        return service.create_transfer(
            user=self.user, source_card=self.card,
            recipient_card_last4="9999", recipient_reference="John",
            send_amount=Decimal("200"), send_currency="USD", receive_currency="AZN",
            idempotency_key=key,
        )

    def test_full_flow_completes_with_ledger(self):
        transfer = self._create()
        service.execute(transfer.id)
        transfer.refresh_from_db()
        self.assertEqual(transfer.status, Status.COMPLETED)
        self.assertTrue(transfer.chain_tx)
        self.assertTrue(transfer.payout_ref)
        # Ledger records every leg.
        accounts = set(transfer.ledger_entries.values_list("account", flat=True))
        self.assertIn("treasury_usdt", accounts)
        self.assertIn("recipient_card", accounts)

    def test_create_is_idempotent(self):
        a = self._create(key="same")
        b = self._create(key="same")
        self.assertEqual(a.id, b.id)

    def test_kyc_required_blocks_execution(self):
        self.user.kyc_status = "unverified"
        self.user.save()
        transfer = self._create(key="nokyc")
        with self.assertRaises(service.KycRequired):
            service.execute(transfer.id)


@override_settings(DEBUG=True)
class ApiEndToEndTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def _login(self, phone="+994500000009"):
        r = self.client.post("/api/v1/auth/request-otp/", {"phone": phone})
        code = r.json()["debug_code"]
        r = self.client.post("/api/v1/auth/verify-otp/", {"phone": phone, "code": code})
        token = r.json()["token"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token}")
        return phone

    def test_otp_login_then_quote(self):
        self._login()
        r = self.client.post(
            "/api/v1/quotes/",
            {"send_amount": "200", "send_currency": "USD", "receive_currency": "AZN"},
            format="json",
        )
        self.assertEqual(r.status_code, 200)
        self.assertIn("network", r.json())

    def test_full_transfer_via_api(self):
        phone = self._login()
        user = User.objects.get(phone=phone)
        user.kyc_status = "verified"
        user.save()

        card = self.client.post(
            "/api/v1/wallets/cards/",
            {"provider_token": "tok_x", "brand": "Visa", "last4": "1436"},
            format="json",
        ).json()

        r = self.client.post(
            "/api/v1/transfers/",
            {
                "source_card_id": card["id"], "recipient_card_last4": "9999",
                "send_amount": "200", "send_currency": "USD",
                "receive_currency": "AZN", "idempotency_key": "api-1",
            },
            format="json",
        )
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()["status"], Status.COMPLETED)
