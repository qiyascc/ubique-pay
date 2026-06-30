from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from ubique.wallets.cards import tokenize_card

User = get_user_model()


class TokenizeTests(TestCase):
    def test_visa_is_tokenized(self):
        token, last4, brand = tokenize_card("4111 1111 1111 1111")
        self.assertEqual(last4, "1111")
        self.assertEqual(brand, "Visa")
        self.assertTrue(token.startswith("rct_"))

    def test_mastercard_brand(self):
        _, last4, brand = tokenize_card("5555555555554444")
        self.assertEqual(last4, "4444")
        self.assertEqual(brand, "Mastercard")

    def test_invalid_number_rejected(self):
        with self.assertRaises(ValueError):
            tokenize_card("1234")


class RecipientApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(phone="+994500000301")
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_create_recipient_tokenizes_and_hides_pan(self):
        r = self.client.post(
            "/api/v1/wallets/recipients/",
            {"name": "Ana", "card_number": "4111111111111111"}, format="json",
        )
        self.assertEqual(r.status_code, 201)
        body = r.json()
        self.assertEqual(body["last4"], "1111")
        self.assertEqual(body["brand"], "Visa")
        self.assertNotIn("card_number", body)  # write-only, never echoed

    def test_invalid_card_rejected(self):
        r = self.client.post(
            "/api/v1/wallets/recipients/",
            {"name": "Bad", "card_number": "1234"}, format="json",
        )
        self.assertEqual(r.status_code, 400)
