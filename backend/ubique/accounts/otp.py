"""One-time-passcode helpers (cache-backed).

In production the code is delivered by an SMS provider; here it is returned in
the API response when DEBUG is on so the flow can be exercised end to end.
"""

import secrets

from django.core.cache import cache

_TTL = 300  # seconds
_PREFIX = "otp:"


def issue(phone: str) -> str:
    code = f"{secrets.randbelow(10000):04d}"
    cache.set(_PREFIX + phone, code, _TTL)
    return code


def verify(phone: str, code: str) -> bool:
    expected = cache.get(_PREFIX + phone)
    if expected is None or code != expected:
        return False
    cache.delete(_PREFIX + phone)  # single use
    return True
