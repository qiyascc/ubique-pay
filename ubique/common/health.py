"""Liveness and readiness probes (unauthenticated, no PII)."""

from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse


def healthz(request):
    """Liveness — the process is up."""
    return JsonResponse({"status": "ok"})


def readyz(request):
    """Readiness — dependencies (DB + cache) are reachable."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        cache.set("readyz", "1", 5)
        cache.get("readyz")
    except Exception as exc:  # noqa: BLE001 - report the dependency failure
        return JsonResponse({"status": "not-ready", "error": str(exc)}, status=503)
    return JsonResponse({"status": "ready"})
