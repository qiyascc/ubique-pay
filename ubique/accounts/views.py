from django.conf import settings
from rest_framework import serializers, status
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from . import otp
from .models import User


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


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        u = request.user
        return Response({"phone": u.phone, "kyc_status": u.kyc_status})
