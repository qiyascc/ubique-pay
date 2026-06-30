"""One-time-passcode helpers (cache-backed) with anti-abuse limits.

In production the code is delivered by an SMS provider; here it is returned in
the API/UI when DEBUG is on so the flow can be exercised end to end.
"""

import secrets

from django.conf import settings
from django.core.cache import cache

_TTL = 300  # code lifetime, seconds
_CODE = "otp:code:"
_SENDS = "otp:sends:"      # issues per phone per hour
_ATTEMPTS = "otp:tries:"   # wrong attempts per code


class OtpError(Exception):
    pass


class RateLimited(OtpError):
    pass


def issue(phone: str) -> str:
    limit = settings.UBIQUE["OTP_MAX_PER_HOUR"]
    sends = cache.get(_SENDS + phone, 0)
    if sends >= limit:
        raise RateLimited("Too many codes requested. Try again later.")
    cache.set(_SENDS + phone, sends + 1, 3600)

    code = f"{secrets.randbelow(1000000):06d}"
    cache.set(_CODE + phone, code, _TTL)
    cache.delete(_ATTEMPTS + phone)
    return code


def verify(phone: str, code: str) -> bool:
    expected = cache.get(_CODE + phone)
    if expected is None:
        return False

    tries = cache.get(_ATTEMPTS + phone, 0)
    if tries >= settings.UBIQUE["OTP_MAX_ATTEMPTS"]:
        cache.delete(_CODE + phone)  # burn the code after too many tries
        raise RateLimited("Too many incorrect attempts. Request a new code.")

    if not secrets.compare_digest(code, expected):
        cache.set(_ATTEMPTS + phone, tries + 1, _TTL)
        return False

    cache.delete(_CODE + phone)
    cache.delete(_ATTEMPTS + phone)
    return True
