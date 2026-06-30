"""Pluggable end-user notifications (separate from integrator webhooks).

Configure channels via ``UBIQUE["NOTIFIERS"]`` (dotted paths). A failing
channel never breaks the request.
"""

import json
import logging
import urllib.parse
import urllib.request
from abc import ABC, abstractmethod

from django.conf import settings
from django.utils.module_loading import import_string

logger = logging.getLogger("ubique")


class Notifier(ABC):
    @abstractmethod
    def send(self, user, event: str, message: str): ...


class ConsoleNotifier(Notifier):
    def send(self, user, event, message):
        logger.info("notify[%s] %s: %s", event, user, message)


class TelegramNotifier(Notifier):
    """DMs the user via the bot (requires user.telegram_id + TELEGRAM_BOT_TOKEN)."""

    def send(self, user, event, message):
        token = settings.TELEGRAM_BOT_TOKEN
        chat_id = getattr(user, "telegram_id", None)
        if not token or not chat_id:
            return
        data = urllib.parse.urlencode({"chat_id": chat_id, "text": message}).encode()
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        req = urllib.request.Request(url, data=data, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:  # nosec B310
            json.loads(resp.read().decode())


def dispatch(user, event: str, message: str):
    for path in settings.UBIQUE.get("NOTIFIERS", []):
        try:
            import_string(path)().send(user, event, message)
        except Exception as exc:  # noqa: BLE001 - a channel must never break the flow
            logger.warning("notifier %s failed: %s", path, exc)
