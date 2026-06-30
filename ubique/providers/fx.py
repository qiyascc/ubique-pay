"""Multi-source FX oracle with caching.

Aggregates several rate sources (median) and caches the result per pair for
``FX_CACHE_TTL`` seconds, so a busy quote endpoint hits the upstreams once per
window instead of on every request. Sources are pluggable via
``UBIQUE["FX_SOURCES"]``.
"""

from abc import ABC, abstractmethod
from decimal import Decimal

from django.conf import settings
from django.core.cache import cache
from django.utils.module_loading import import_string

from .base import FxOracle

# Mid-market base table shared by the demo sources (each adds a small jitter).
_BASE = {
    ("USDT", "USD"): Decimal("1.00"), ("USDT", "EUR"): Decimal("0.92"),
    ("USDT", "AZN"): Decimal("1.70"), ("USDT", "TRY"): Decimal("32.0"),
    ("USD", "USDT"): Decimal("1.00"), ("EUR", "USDT"): Decimal("1.087"),
    ("AZN", "USDT"): Decimal("0.588"), ("TRY", "USDT"): Decimal("0.03125"),
}


class FxSource(ABC):
    @abstractmethod
    def rate(self, base: str, quote: str) -> Decimal: ...


class _JitterSource(FxSource):
    factor = Decimal("1")

    def rate(self, base, quote):
        if base == quote:
            return Decimal("1")
        try:
            return _BASE[(base, quote)] * self.factor
        except KeyError as exc:
            raise ValueError(f"No FX rate for {base}->{quote}") from exc


class SourceA(_JitterSource):
    factor = Decimal("1.002")


class SourceB(_JitterSource):
    factor = Decimal("0.998")


def _median(values):
    vs = sorted(values)
    n = len(vs)
    mid = n // 2
    return vs[mid] if n % 2 else (vs[mid - 1] + vs[mid]) / 2


class CachingMultiSourceFxOracle(FxOracle):
    def __init__(self):
        self.sources = [import_string(p)() for p in settings.UBIQUE["FX_SOURCES"]]
        self.ttl = settings.UBIQUE["FX_CACHE_TTL"]

    def rate(self, base, quote):
        if base == quote:
            return Decimal("1")

        def compute():
            return _median([s.rate(base, quote) for s in self.sources])

        return cache.get_or_set(f"fx:{base}:{quote}", compute, self.ttl)
