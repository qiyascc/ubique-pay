import json
import time
from decimal import Decimal

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from .models import User
from .telegram import TelegramAuthError, sign_init_data, validate_init_data

BOT_TOKEN = "123456:TEST-bot-token-abcDEF"


def _init_data(user_id=4242, username="qiyas", token=BOT_TOKEN, auth_date=None):
    fields = {
        "auth_date": str(auth_date or int(time.time())),
        "query_id": "AAH",
        "user": json.dumps({"id": user_id, "first_name": "Q", "username": username}),
    }
    return sign_init_data(fields, token)


class TelegramInitDataTests(TestCase):
    def test_valid_init_data_returns_user(self):
        user = validate_init_data(_init_data(), BOT_TOKEN)
        self.assertEqual(user["id"], 4242)
        self.assertEqual(user["username"], "qiyas")

    def test_tampered_hash_is_rejected(self):
        bad = _init_data()[:-4] + "0000"
        with self.assertRaises(TelegramAuthError):
            validate_init_data(bad, BOT_TOKEN)

    def test_wrong_bot_token_is_rejected(self):
        with self.assertRaises(TelegramAuthError):
            validate_init_data(_init_data(), "999:OTHER-token")

    def test_expired_init_data_is_rejected(self):
        old = _init_data(auth_date=int(time.time()) - 100000)
        with self.assertRaises(TelegramAuthError):
            validate_init_data(old, BOT_TOKEN, max_age=86400)


@override_settings(TELEGRAM_BOT_TOKEN=BOT_TOKEN)
class TelegramAuthApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_telegram_login_creates_user_and_token(self):
        r = self.client.post(
            "/api/v1/auth/telegram/", {"init_data": _init_data(user_id=777)}, format="json"
        )
        self.assertEqual(r.status_code, 200)
        self.assertIn("token", r.json())
        self.assertTrue(User.objects.filter(telegram_id=777).exists())

    def test_invalid_init_data_is_401(self):
        r = self.client.post(
            "/api/v1/auth/telegram/", {"init_data": "user=x&hash=bad"}, format="json"
        )
        self.assertEqual(r.status_code, 401)


class TonAmountTests(TestCase):
    def test_usdt_to_jetton_units(self):
        from ubique.providers.real import TonChainSender
        self.assertEqual(TonChainSender.to_jetton_units(Decimal("1.5")), 1_500_000)
        self.assertEqual(TonChainSender.to_jetton_units("0.000001"), 1)


SUMSUB_SECRET = "sumsub-webhook-secret"


@override_settings(SUMSUB_WEBHOOK_SECRET=SUMSUB_SECRET)
class SumsubWebhookTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(phone="+994500007777")

    def _post(self, answer, sign=True, alg="HMAC_SHA256_HEX"):
        import hashlib
        import hmac as _hmac
        body = json.dumps({
            "externalUserId": str(self.user.id),
            "type": "applicantReviewed",
            "reviewResult": {"reviewAnswer": answer},
        }).encode()
        algo = {"HMAC_SHA256_HEX": hashlib.sha256, "HMAC_SHA512_HEX": hashlib.sha512}[alg]
        digest = _hmac.new(SUMSUB_SECRET.encode(), body, algo).hexdigest()
        return self.client.post(
            "/api/v1/auth/kyc/webhook/", data=body, content_type="application/json",
            HTTP_X_PAYLOAD_DIGEST=(digest if sign else "bad"),
            HTTP_X_PAYLOAD_DIGEST_ALG=alg,
        )

    def test_green_verifies_user(self):
        r = self._post("GREEN")
        self.assertEqual(r.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.kyc_status, "verified")

    def test_red_rejects_user(self):
        self._post("RED")
        self.user.refresh_from_db()
        self.assertEqual(self.user.kyc_status, "rejected")

    def test_bad_signature_is_401(self):
        r = self._post("GREEN", sign=False)
        self.assertEqual(r.status_code, 401)
        self.user.refresh_from_db()
        self.assertEqual(self.user.kyc_status, "unverified")

    def test_sha512_algorithm_supported(self):
        r = self._post("GREEN", alg="HMAC_SHA512_HEX")
        self.assertEqual(r.status_code, 200)


@override_settings(
    TELEGRAM_BOT_TOKEN=BOT_TOKEN,
    KYC_PROVIDER="ubique.accounts.kyc.DemoKycProvider",
)
class MiniAppJourneyTests(TestCase):
    """The exact API sequence the Telegram Mini App performs."""

    def setUp(self):
        self.c = APIClient()

    def test_full_mini_app_journey(self):
        # 1) Telegram sign-in
        r = self.c.post(
            "/api/v1/auth/telegram/", {"init_data": _init_data(user_id=555)}, format="json"
        )
        self.c.credentials(HTTP_AUTHORIZATION="Token " + r.json()["token"])

        # 2) KYC gate → start (demo provider verifies)
        self.assertEqual(self.c.get("/api/v1/auth/me/").json()["kyc_status"], "unverified")
        self.c.post("/api/v1/auth/kyc/start/")
        self.assertEqual(self.c.get("/api/v1/auth/me/").json()["kyc_status"], "verified")

        # 3) add a card
        card = self.c.post(
            "/api/v1/wallets/cards/",
            {"brand": "Visa", "last4": "1436", "provider_token": ""}, format="json",
        ).json()

        # 4) quote + 5) confirm transfer
        q = self.c.post(
            "/api/v1/quotes/",
            {"send_amount": "200", "send_currency": "USD", "receive_currency": "AZN"},
            format="json",
        )
        self.assertEqual(q.status_code, 200)
        t = self.c.post(
            "/api/v1/transfers/",
            {
                "source_card_id": card["id"], "recipient_card_last4": "9999",
                "send_amount": "200", "send_currency": "USD",
                "receive_currency": "AZN", "idempotency_key": "mj-1",
            }, format="json",
        )
        self.assertEqual(t.status_code, 201)
        self.assertEqual(t.json()["status"], "completed")
