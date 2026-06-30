"""Real Telegram Mini App ``initData`` validation.

Implements the official algorithm
(https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app):

    secret_key = HMAC_SHA256(key="WebAppData", msg=bot_token)
    check_hash = HMAC_SHA256(key=secret_key, msg=data_check_string)

where ``data_check_string`` is every field except ``hash`` sorted by key and
joined as ``key=value`` with newlines. The signature proves the payload came
from Telegram and was not tampered with.
"""

import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl


class TelegramAuthError(Exception):
    pass


def validate_init_data(init_data: str, bot_token: str, max_age: int = 86400) -> dict:
    """Validate ``initData`` and return the parsed Telegram ``user`` dict."""
    if not bot_token:
        raise TelegramAuthError("Telegram bot token is not configured.")

    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = pairs.pop("hash", None)
    if not received_hash:
        raise TelegramAuthError("Missing hash.")

    data_check_string = "\n".join(
        f"{k}={pairs[k]}" for k in sorted(pairs)
    )
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected, received_hash):
        raise TelegramAuthError("Invalid signature.")

    auth_date = int(pairs.get("auth_date", "0"))
    if max_age and (time.time() - auth_date) > max_age:
        raise TelegramAuthError("initData has expired.")

    user_raw = pairs.get("user")
    if not user_raw:
        raise TelegramAuthError("No user in initData.")
    try:
        return json.loads(user_raw)
    except json.JSONDecodeError as exc:
        raise TelegramAuthError("Malformed user payload.") from exc


def sign_init_data(fields: dict, bot_token: str) -> str:
    """Produce a valid signed initData string (used in tests/tooling)."""
    data_check_string = "\n".join(f"{k}={fields[k]}" for k in sorted(fields))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    h = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    from urllib.parse import urlencode

    return urlencode({**fields, "hash": h})
