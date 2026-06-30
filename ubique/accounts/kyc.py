"""Pluggable KYC providers.

The web/Mini App calls ``start(user)`` to begin verification; real providers
return an SDK token/URL and later confirm via a signed webhook. Swap providers
with the ``KYC_PROVIDER`` setting.

Note on "Telegram's own KYC": Telegram **Passport** lets users share ID
documents in one tap, but it only *collects* (encrypted) documents — it does
not run liveness/AML checks, and decrypting its credentials (RSA-OAEP + AES) is
more work than a hosted SDK. Services like EXMO pair Telegram Passport with
Sumsub for the actual verification. So Sumsub is the real KYC engine here;
Passport could later be added as a document front-end.
"""

import hashlib
import hmac
import os
import time
from abc import ABC, abstractmethod

from django.conf import settings
from django.utils.module_loading import import_string

from .models import KycStatus


class KycProvider(ABC):
    name = "kyc"

    @abstractmethod
    def start(self, user) -> dict:
        """Begin verification; return a dict for the client (status, token…)."""

    def refresh_token(self, user):
        """Return a fresh SDK access token (for the WebSDK expiry callback)."""
        return None


class DemoKycProvider(KycProvider):
    """Instantly verifies — for local/demo use only."""

    name = "demo"

    def start(self, user):
        user.kyc_status = KycStatus.VERIFIED
        user.save(update_fields=["kyc_status"])
        return {"provider": "demo", "status": user.kyc_status, "sdk_token": None}


class SumsubKycProvider(KycProvider):
    """Real KYC via Sumsub.

    Env: SUMSUB_APP_TOKEN, SUMSUB_SECRET_KEY, SUMSUB_LEVEL_NAME,
         SUMSUB_WEBHOOK_SECRET. ``start`` creates/links an applicant and returns
         an access token for the Sumsub WebSDK (open it inside the Mini App).
         A signed ``applicantReviewed`` webhook flips the user to verified.
    """

    name = "sumsub"
    BASE = "https://api.sumsub.com"

    def __init__(self):
        self.app_token = os.environ.get("SUMSUB_APP_TOKEN", "")
        self.secret = os.environ.get("SUMSUB_SECRET_KEY", "")
        self.level = os.environ.get("SUMSUB_LEVEL_NAME", "basic-kyc-level")
        if not self.app_token or not self.secret:
            from django.core.exceptions import ImproperlyConfigured
            raise ImproperlyConfigured("Sumsub needs SUMSUB_APP_TOKEN and SUMSUB_SECRET_KEY.")

    def _signed_request(self, method, path, body=b""):
        import urllib.request

        ts = str(int(time.time()))
        sig = hmac.new(
            self.secret.encode(), (ts + method + path).encode() + body, hashlib.sha256
        ).hexdigest()
        req = urllib.request.Request(
            self.BASE + path, data=body or None, method=method,
            headers={
                "X-App-Token": self.app_token,
                "X-App-Access-Sig": sig,
                "X-App-Access-Ts": ts,
                "Content-Type": "application/json",
            },
        )
        import json
        # URL is built from the hardcoded https Sumsub base; safe scheme.
        with urllib.request.urlopen(req, timeout=20) as resp:  # nosec B310
            return json.loads(resp.read().decode())

    def _access_token(self, user, ttl=600):
        path = (
            f"/resources/accessTokens?userId={user.id}"
            f"&levelName={self.level}&ttlInSecs={ttl}"
        )
        return self._signed_request("POST", path).get("token")

    def start(self, user):
        token = self._access_token(user)
        if user.kyc_status == KycStatus.UNVERIFIED:
            user.kyc_status = KycStatus.PENDING
            user.save(update_fields=["kyc_status"])
        return {"provider": "sumsub", "status": user.kyc_status, "sdk_token": token}

    def refresh_token(self, user):
        return self._access_token(user)


def get_provider() -> KycProvider:
    return import_string(settings.KYC_PROVIDER)()
