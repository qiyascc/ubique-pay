"""Field-level encryption at rest (Fernet / AES-128-CBC + HMAC).

Sensitive values (card tokens) are encrypted before they hit the database and
decrypted transparently on read. Keys come from ``UBIQUE_FIELD_KEYS`` (the first
is primary, the rest enable rotation via MultiFernet); if unset, a key is
derived from ``SECRET_KEY`` so dev/tests work out of the box.

These fields are never queried by value, so encrypting them does not break any
lookups. Legacy plaintext rows are returned as-is until re-saved.
"""

import base64
import hashlib
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from django.conf import settings
from django.db import models


@lru_cache(maxsize=1)
def _cipher() -> MultiFernet:
    keys = list(getattr(settings, "UBIQUE_FIELD_KEYS", []) or [])
    if not keys:
        # Deterministic fallback derived from SECRET_KEY (stable across restarts).
        derived = base64.urlsafe_b64encode(
            hashlib.sha256(settings.SECRET_KEY.encode()).digest()
        ).decode()
        keys = [derived]
    return MultiFernet([Fernet(k) for k in keys])


class EncryptedCharField(models.CharField):
    """A CharField whose value is encrypted at rest."""

    def from_db_value(self, value, expression, connection):
        if value is None or value == "":
            return value
        try:
            return _cipher().decrypt(value.encode()).decode()
        except (InvalidToken, ValueError):
            return value  # legacy plaintext, returned until re-saved

    def get_prep_value(self, value):
        value = super().get_prep_value(value)
        if value is None or value == "":
            return value
        return _cipher().encrypt(str(value).encode()).decode()
