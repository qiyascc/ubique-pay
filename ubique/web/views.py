import uuid

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from ubique.accounts import otp
from ubique.accounts.models import KycStatus, User
from ubique.quotes.engine import build_quote
from ubique.transfers import service
from ubique.transfers.models import Transfer
from ubique.wallets.models import CryptoAccount, PaymentCard

from .forms import CardForm, CodeForm, PhoneForm, SendForm

_AUTH_BACKEND = "django.contrib.auth.backends.ModelBackend"


def landing(request):
    if request.user.is_authenticated:
        return redirect("web:dashboard")
    return render(request, "web/landing.html")


def login_view(request):
    form = PhoneForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        phone = form.cleaned_data["phone"]
        try:
            code = otp.issue(phone)
        except otp.RateLimited as exc:
            messages.error(request, str(exc))
            return render(request, "web/login.html", {"form": form})
        request.session["otp_phone"] = phone
        if settings.DEBUG:
            messages.info(request, f"Demo code: {code}")
        return redirect("web:verify")
    return render(request, "web/login.html", {"form": form})


def verify_view(request):
    phone = request.session.get("otp_phone")
    if not phone:
        return redirect("web:login")
    form = CodeForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            ok = otp.verify(phone, form.cleaned_data["code"])
        except otp.RateLimited as exc:
            messages.error(request, str(exc))
            return redirect("web:login")
        if not ok:
            messages.error(request, "Invalid or expired code.")
        else:
            user, _ = User.objects.get_or_create(phone=phone)
            login(request, user, backend=_AUTH_BACKEND)
            request.session.pop("otp_phone", None)
            return redirect("web:dashboard")
    return render(request, "web/verify.html", {"form": form, "phone": phone})


def logout_view(request):
    logout(request)
    return redirect("web:landing")


@login_required
def dashboard(request):
    return render(request, "web/dashboard.html", {
        "transfers": request.user.transfers.all()[:10],
        "cards": request.user.cards.all(),
        "crypto_accounts": request.user.crypto_accounts.all(),
        "kyc_verified": request.user.is_kyc_verified,
    })


@login_required
def add_card(request):
    form = CardForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        PaymentCard.objects.create(
            user=request.user,
            brand=form.cleaned_data["brand"],
            last4=form.cleaned_data["last4"],
            provider_token=form.cleaned_data["provider_token"] or f"tok_{uuid.uuid4().hex[:12]}",
        )
        messages.success(request, "Card added.")
        return redirect("web:dashboard")
    return render(request, "web/form.html", {"form": form, "title": "Add a card"})


@login_required
def verify_kyc(request):
    # Demo only: real KYC is delegated to the on-ramp/KYC vendor.
    if request.method == "POST":
        request.user.kyc_status = KycStatus.VERIFIED
        request.user.save(update_fields=["kyc_status"])
        messages.success(request, "Identity verified (demo).")
    return redirect("web:dashboard")


@login_required
def send(request):
    cards = request.user.cards.all()
    if not cards:
        messages.error(request, "Add a card before sending money.")
        return redirect("web:add_card")

    choices = [(c.id, f"{c.brand} ****{c.last4}") for c in cards]
    form = SendForm(request.POST or None, card_choices=choices)
    quote = None

    if request.method == "POST" and form.is_valid():
        cd = form.cleaned_data
        action = request.POST.get("action", "preview")
        try:
            quote = build_quote(
                send_amount=cd["send_amount"],
                send_currency=cd["send_currency"],
                receive_currency=cd["receive_currency"],
            )
        except ValueError as exc:
            messages.error(request, str(exc))
            return render(request, "web/send.html", {"form": form, "quote": None})

        if action == "confirm":
            card = get_object_or_404(PaymentCard, id=cd["source_card"], user=request.user)
            try:
                transfer = service.create_transfer(
                    user=request.user, source_card=card,
                    recipient_card_last4=cd["recipient_card_last4"],
                    recipient_reference=cd.get("recipient_reference", ""),
                    send_amount=cd["send_amount"], send_currency=cd["send_currency"],
                    receive_currency=cd["receive_currency"],
                    idempotency_key=uuid.uuid4().hex,
                )
            except (service.LimitExceeded, service.ComplianceReject) as exc:
                messages.error(request, str(exc))
                return render(request, "web/send.html", {"form": form, "quote": quote})
            try:
                service.execute(transfer.id)
            except (service.KycRequired, service.LiquidityError) as exc:
                messages.error(request, str(exc))
                return redirect("web:dashboard")
            except Exception:  # noqa: BLE001 - marked FAILED inside execute
                messages.error(request, "Transfer failed. No funds were moved.")
            return redirect("web:transfer_detail", pk=transfer.id)

    return render(request, "web/send.html", {"form": form, "quote": quote})


@login_required
def transfer_detail(request, pk):
    transfer = get_object_or_404(Transfer, pk=pk, user=request.user)
    return render(request, "web/transfer_detail.html", {"t": transfer})


def miniapp(request):
    """The Telegram Mini App page (authenticates via signed initData)."""
    response = render(request, "web/miniapp.html")
    # Relaxed CSP only for this page: Telegram SDK + TON Connect bridges.
    response["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' https://telegram.org https://unpkg.com https://static.sumsub.com; "
        "style-src 'self' 'unsafe-inline' https://static.sumsub.com; "
        "img-src 'self' data: https:; "
        "media-src https://*.sumsub.com blob:; "
        "worker-src 'self' blob:; "
        "connect-src 'self' https://*.tonapi.io https://bridge.tonapi.io "
        "wss://bridge.tonapi.io https://*.ton.org "
        "https://api.sumsub.com https://*.sumsub.com wss://*.sumsub.com; "
        "frame-src https://*.tonapi.io https://*.sumsub.com; "
        "frame-ancestors https://web.telegram.org https://*.telegram.org"
    )
    return response


def tonconnect_manifest(request):
    base = settings.PUBLIC_BASE_URL.rstrip("/")
    return JsonResponse({
        "url": base,
        "name": "Ubique Pay",
        "iconUrl": base + "/static/icon.png",
        "termsOfUseUrl": base + "/",
        "privacyPolicyUrl": base + "/",
    })
