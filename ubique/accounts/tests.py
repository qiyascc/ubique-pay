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
