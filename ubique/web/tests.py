from django.core.cache import cache
from django.test import TestCase, override_settings

from ubique.accounts.models import KycStatus, User


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

        # 4) preview a quote
        base = {
            "source_card": card.id, "send_amount": "200", "send_currency": "USD",
            "receive_currency": "AZN", "recipient_card_last4": "9999",
            "recipient_reference": "John",
        }
        r = self.client.post("/send/", {**base, "action": "preview"})
        self.assertContains(r, "Recipient gets")

        # 5) confirm -> transfer completes
        r = self.client.post("/send/", {**base, "action": "confirm"})
        self.assertEqual(r.status_code, 302)
        detail = self.client.get(r["Location"])
        self.assertContains(detail, "Completed")
