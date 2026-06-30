from rest_framework import generics, status
from rest_framework.response import Response

from ubique.wallets.models import PaymentCard

from . import service
from .models import Transfer
from .serializers import CreateTransferSerializer, TransferSerializer


class TransferListCreate(generics.ListCreateAPIView):
    serializer_class = TransferSerializer

    def get_queryset(self):
        return Transfer.objects.filter(user=self.request.user)

    def create(self, request, *args, **kwargs):
        payload = CreateTransferSerializer(data=request.data, context={"request": request})
        payload.is_valid(raise_exception=True)
        v = payload.validated_data
        card = PaymentCard.objects.get(id=v["source_card_id"], user=request.user)

        try:
            transfer = service.create_transfer(
                user=request.user,
                source_card=card,
                recipient_card_last4=v["recipient_card_last4"],
                recipient_reference=v.get("recipient_reference", ""),
                send_amount=v["send_amount"],
                send_currency=v["send_currency"].upper(),
                receive_currency=v["receive_currency"].upper(),
                idempotency_key=v["idempotency_key"],
            )
        except (service.LimitExceeded, service.ComplianceReject) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        try:
            service.execute(transfer.id)
        except service.KycRequired as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except Exception:  # noqa: BLE001 - transfer is marked FAILED inside execute
            pass

        transfer.refresh_from_db()
        return Response(TransferSerializer(transfer).data, status=status.HTTP_201_CREATED)


class TransferDetail(generics.RetrieveAPIView):
    serializer_class = TransferSerializer

    def get_queryset(self):
        return Transfer.objects.filter(user=self.request.user)
