from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ubique.wallets.models import PaymentCard

from . import service
from .models import Transfer
from .serializers import CreateTransferSerializer, TransferSerializer


class TransferListCreate(generics.ListCreateAPIView):
    serializer_class = TransferSerializer

    def get_queryset(self):
        return Transfer.objects.filter(user=self.request.user)

    def _resolve_recipient(self, request, v):
        """Return (token, last4, brand, name) from a saved recipient, a fresh
        card number, or a legacy last-4."""
        from ubique.wallets.cards import tokenize_card
        from ubique.wallets.models import Recipient

        if v.get("recipient_id"):
            r = Recipient.objects.filter(id=v["recipient_id"], user=request.user).first()
            if not r:
                raise ValueError("Recipient not found.")
            return r.card_token, r.last4, r.brand, v.get("recipient_name") or r.name
        if v.get("recipient_card_number"):
            token, last4, brand = tokenize_card(v["recipient_card_number"])
            return token, last4, brand, v.get("recipient_name", "")
        return "", v.get("recipient_card_last4", ""), "", v.get("recipient_name") or v.get("recipient_reference", "")

    def create(self, request, *args, **kwargs):
        payload = CreateTransferSerializer(data=request.data, context={"request": request})
        payload.is_valid(raise_exception=True)
        v = payload.validated_data
        card = PaymentCard.objects.get(id=v["source_card_id"], user=request.user)

        # Idempotency-Key header (preferred) or body key.
        idem = request.headers.get("Idempotency-Key") or v.get("idempotency_key")
        if not idem:
            return Response(
                {"detail": "Idempotency key required (Idempotency-Key header or body)."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            token, last4, brand, name = self._resolve_recipient(request, v)
            transfer = service.create_transfer(
                user=request.user,
                source_card=card,
                recipient_card_last4=last4,
                recipient_card_token=token,
                recipient_brand=brand,
                recipient_reference=name,
                send_amount=v["send_amount"],
                send_currency=v["send_currency"].upper(),
                receive_currency=v["receive_currency"].upper(),
                idempotency_key=idem,
            )
        except (service.LimitExceeded, service.ComplianceReject) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        try:
            service.execute(transfer.id)
        except (service.KycRequired, service.LiquidityError) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except Exception:  # noqa: BLE001 - transfer is marked FAILED inside execute
            pass

        transfer.refresh_from_db()
        return Response(TransferSerializer(transfer).data, status=status.HTTP_201_CREATED)


class TransferDetail(generics.RetrieveAPIView):
    serializer_class = TransferSerializer

    def get_queryset(self):
        return Transfer.objects.filter(user=self.request.user)


class TransferReleaseView(APIView):
    """A compliance officer releases a transfer held for review, then runs it."""

    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        get_object_or_404(Transfer, pk=pk)
        with transaction.atomic():
            transfer = Transfer.objects.select_for_update().get(pk=pk)
            service.release_for_review(transfer, request.user)
        try:
            service.execute(transfer.id)
        except (service.KycRequired, service.LiquidityError, service.ReviewRequired):
            pass
        except Exception:  # noqa: BLE001 - marked FAILED inside execute
            pass
        transfer.refresh_from_db()
        return Response(TransferSerializer(transfer).data)


class TransferDisputeView(APIView):
    """The sender opens a dispute against their transfer."""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        transfer = get_object_or_404(Transfer, pk=pk, user=request.user)
        reason = (request.data.get("reason") or "").strip()
        if not reason:
            return Response({"detail": "A reason is required."},
                            status=status.HTTP_400_BAD_REQUEST)
        dispute = service.open_dispute(transfer, reason, request.user)
        return Response({"dispute_id": dispute.id, "status": dispute.status},
                        status=status.HTTP_201_CREATED)


class TransferApproveView(APIView):
    """A treasury signer approves a multisig-gated transfer."""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        get_object_or_404(Transfer, pk=pk)
        try:
            with transaction.atomic():
                transfer = Transfer.objects.select_for_update().get(pk=pk)
                service.approve_onchain(transfer, request.user)
        except service.NotASigner as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        transfer.refresh_from_db()
        return Response(TransferSerializer(transfer).data)
