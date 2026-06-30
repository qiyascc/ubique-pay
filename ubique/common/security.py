"""Adds defence-in-depth response headers not covered by Django core."""

from django.conf import settings


class SecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        csp = getattr(settings, "CONTENT_SECURITY_POLICY", None)
        if csp:
            response.setdefault("Content-Security-Policy", csp)
        response.setdefault(
            "Permissions-Policy",
            "geolocation=(), microphone=(), camera=(), payment=()",
        )
        response.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        response.setdefault("X-Content-Type-Options", "nosniff")
        return response
