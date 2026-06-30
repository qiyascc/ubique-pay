from django.conf import settings
from rest_framework import serializers, status
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

import hashlib
import hmac
import json

from . import otp
from .kyc import get_provider
from .models import KycStatus, User
from .telegram import TelegramAuthError, validate_init_data


class PhoneSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=20)


class VerifySerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=20)
    code = serializers.CharField(max_length=6)


class RequestOtpView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        data = PhoneSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            code = otp.issue(data.validated_data["phone"])
        except otp.RateLimited as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_429_TOO_MANY_REQUESTS)
        body = {"detail": "OTP sent."}
        if settings.DEBUG:  # convenience for local/demo use only
            body["debug_code"] = code
        return Response(body)


class VerifyOtpView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        data = VerifySerializer(data=request.data)
        data.is_valid(raise_exception=True)
        phone = data.validated_data["phone"]
        try:
            ok = otp.verify(phone, data.validated_data["code"])
        except otp.RateLimited as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_429_TOO_MANY_REQUESTS)
        if not ok:
            return Response(
                {"detail": "Invalid or expired code."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user, _ = User.objects.get_or_create(phone=phone)
        token, _ = Token.objects.get_or_create(user=user)
        return Response({"token": token.key, "kyc_status": user.kyc_status})


class TelegramAuthView(APIView):
    """Authenticate a Telegram Mini App user from validated initData."""

    permission_classes = [AllowAny]

    def post(self, request):
        init_data = request.data.get("init_data", "")
        try:
            tg_user = validate_init_data(init_data, settings.TELEGRAM_BOT_TOKEN)
        except TelegramAuthError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_401_UNAUTHORIZED)

        user, _ = User.objects.get_or_create(
            telegram_id=tg_user["id"],
            defaults={
                "phone": f"tg:{tg_user['id']}",
                "telegram_username": tg_user.get("username", ""),
            },
        )
        token, _ = Token.objects.get_or_create(user=user)
        return Response({"token": token.key, "kyc_status": user.kyc_status})


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        u = request.user
        return Response({
            "phone": u.phone,
            "telegram_id": u.telegram_id,
            "kyc_status": u.kyc_status,
        })


class KycStartView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        return Response(get_provider().start(request.user))


class SumsubWebhookView(APIView):
    """Sumsub applicant-reviewed webhook (X-Payload-Digest = HMAC-SHA256)."""

    authentication_classes: list = []
    permission_classes = [AllowAny]

    def post(self, request):
        secret = settings.SUMSUB_WEBHOOK_SECRET
        signature = request.headers.get("X-Payload-Digest", "")
        expected = hmac.new(secret.encode(), request.body, hashlib.sha256).hexdigest() if secret else ""
        if not secret or not hmac.compare_digest(expected, signature):
            return Response({"detail": "Invalid signature."}, status=status.HTTP_401_UNAUTHORIZED)

        data = json.loads(request.body.decode() or "{}")
        external_id = data.get("externalUserId")
        answer = (data.get("reviewResult") or {}).get("reviewAnswer")
        user = User.objects.filter(id=external_id).first()
        if user:
            if answer == "GREEN":
                user.kyc_status = KycStatus.VERIFIED
            elif answer == "RED":
                user.kyc_status = KycStatus.REJECTED
            user.save(update_fields=["kyc_status"])
        return Response({"detail": "ok"})
