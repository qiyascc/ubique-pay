"""Request correlation IDs + structured-log support.

Every request gets a request id (from an inbound ``X-Request-ID`` or a fresh
one); it is attached to the request, echoed in the response, exposed to log
records via a contextvar, and available to handlers for tracing a request end
to end across logs.
"""

import contextvars
import logging
import uuid

_request_id: contextvars.ContextVar = contextvars.ContextVar("request_id", default="-")


def current_request_id() -> str:
    return _request_id.get()


class RequestIDMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:16]
        request.request_id = rid
        token = _request_id.set(rid)
        try:
            response = self.get_response(request)
        finally:
            _request_id.reset(token)
        response["X-Request-ID"] = rid
        return response


class RequestIDLogFilter(logging.Filter):
    """Injects ``request_id`` into every log record so formatters can use it."""

    def filter(self, record):
        record.request_id = _request_id.get()
        return True
