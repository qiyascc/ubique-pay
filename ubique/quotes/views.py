from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .engine import build_quote


class QuoteRequestSerializer(serializers.Serializer):
    send_amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0)
    send_currency = serializers.CharField(max_length=8)
    receive_currency = serializers.CharField(max_length=8)


class QuoteView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = QuoteRequestSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            quote = build_quote(
                send_amount=data.validated_data["send_amount"],
                send_currency=data.validated_data["send_currency"].upper(),
                receive_currency=data.validated_data["receive_currency"].upper(),
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(quote.as_dict())
