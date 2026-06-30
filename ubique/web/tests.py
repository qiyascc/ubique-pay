from django.core.cache import cache
from django.test import TestCase, override_settings

from ubique.accounts.models import KycStatus, User


class StatementTests(TestCase):
    def test_statement_csv_download(self):
        user = User.objects.create_user(phone="+994500000501")
        self.client.force_login(user)
        r = self.client.get("/statement.csv")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "text/csv")
        self.assertIn("attachment", r["Content-Disposition"])


class ObservabilityTests(TestCase):
    def test_healthz_ok(self):
        r = self.client.get("/healthz")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "ok")
        self.assertIn("X-Request-ID", r)

    def test_readyz_checks_dependencies(self):
        r = self.client.get("/readyz")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "ready")

    def test_request_id_propagates(self):
        r = self.client.get("/healthz", HTTP_X_REQUEST_ID="trace-abc")
        self.assertEqual(r["X-Request-ID"], "trace-abc")


@override_settings(DEBUG=True)
class OpsDashboardTests(TestCase):
    def test_staff_sees_dashboard(self):
        User.objects.create_user(phone="+994500000010")  # ensure a user exists
        staff = User.objects.create_superuser(phone="+994500000011", password="Str0ng!Pass99")
        self.client.force_login(staff)
        r = self.client.get("/ops/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Operations")
        self.assertContains(r, "Status mix")

    def test_non_staff_blocked(self):
        user = User.objects.create_user(phone="+994500000012")
        self.client.force_login(user)
        r = self.client.get("/ops/")
        self.assertEqual(r.status_code, 302)  # redirected to admin login


@override_settings(DEBUG=True)
class WebFlowTests(TestCase):
    def test_landing_renders(self):
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "anyone, anywhere")

    def test_security_headers_present(self):
        r = self.client.get("/")
        self.assertIn("Content-Security-Policy", r)
        self.assertEqual(r["X-Frame-Options"], "DENY")

    def test_dashboard_requires_login(self):
        r = self.client.get("/dashboard/")
        self.assertEqual(r.status_code, 302)
        self.assertIn("/login/", r["Location"])

    def test_full_web_journey(self):
        phone = "+994501234567"
        # 1) request OTP
        r = self.client.post("/login/", {"phone": phone})
        self.assertRedirects(r, "/verify/", fetch_redirect_response=False)
        code = cache.get("otp:code:" + phone)
        self.assertIsNotNone(code)

        # 2) verify -> logged in
        r = self.client.post("/verify/", {"code": code})
        self.assertRedirects(r, "/dashboard/", fetch_redirect_response=False)

        # 3) KYC (demo) + add a card
        self.client.post("/kyc/verify/")
        user = User.objects.get(phone=phone)
        self.assertEqual(user.kyc_status, KycStatus.VERIFIED)
        self.client.post("/cards/add/", {"brand": "Visa", "last4": "1436", "provider_token": ""})
        card = user.cards.first()
        self.assertIsNotNone(card)

        # 4) preview a quote (recipient = a fresh, tokenized card number)
        base = {
            "source_card": card.id, "send_amount": "200", "send_currency": "USD",
            "receive_currency": "AZN", "saved_recipient": "",
            "recipient_card_number": "4111111111111111", "recipient_name": "John",
        }
        r = self.client.post("/send/", {**base, "action": "preview"})
        self.assertContains(r, "Recipient gets")

        # 5) confirm -> transfer completes
        r = self.client.post("/send/", {**base, "action": "confirm"})
        self.assertEqual(r.status_code, 302)
        detail = self.client.get(r["Location"])
        self.assertContains(detail, "Completed")
        # The PAN was tokenized to last 4 + brand.
        t = user.transfers.first()
        self.assertEqual(t.recipient_card_last4, "1111")
        self.assertEqual(t.recipient_brand, "Visa")
        self.assertTrue(t.recipient_card_token.startswith("rct_"))
