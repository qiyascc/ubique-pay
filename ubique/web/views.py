import uuid

from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from ubique.accounts import otp
from ubique.accounts.models import KycStatus, User
from ubique.corridors.models import Corridor, TreasuryBalance
from ubique.quotes.engine import build_quote
from ubique.transfers import service
from ubique.transfers.models import Transfer
from ubique.transfers.state import Status
from ubique.wallets.cards import tokenize_card
from ubique.wallets.models import PaymentCard, Recipient

from .forms import CardForm, CodeForm, PhoneForm, RecipientForm, SendForm

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
            from ubique.audit.log import log
            forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
            ip = forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR")
            log("login", actor=user, ip=ip)
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
def recipients(request):
    form = RecipientForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            token, last4, brand = tokenize_card(form.cleaned_data["card_number"])
        except ValueError as exc:
            messages.error(request, str(exc))
            return render(request, "web/recipients.html",
                          {"form": form, "recipients": request.user.recipients.all()})
        Recipient.objects.create(
            user=request.user, name=form.cleaned_data["name"],
            card_token=token, last4=last4, brand=brand,
        )
        messages.success(request, "Recipient saved.")
        return redirect("web:recipients")
    return render(request, "web/recipients.html",
                  {"form": form, "recipients": request.user.recipients.all()})


@login_required
def send(request):
    cards = request.user.cards.all()
    if not cards:
        messages.error(request, "Add a card before sending money.")
        return redirect("web:add_card")

    card_choices = [(c.id, f"{c.brand} ****{c.last4}") for c in cards]
    recipient_choices = [(r.id, f"{r.name} · {r.brand} ····{r.last4}")
                         for r in request.user.recipients.all()]
    form = SendForm(request.POST or None, card_choices=card_choices,
                    recipient_choices=recipient_choices)
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
                token, last4, brand, name = _resolve_web_recipient(request, cd)
                transfer = service.create_transfer(
                    user=request.user, source_card=card,
                    recipient_card_last4=last4, recipient_card_token=token,
                    recipient_brand=brand, recipient_reference=name,
                    send_amount=cd["send_amount"], send_currency=cd["send_currency"],
                    receive_currency=cd["receive_currency"],
                    idempotency_key=uuid.uuid4().hex,
                )
            except (service.LimitExceeded, service.ComplianceReject, ValueError) as exc:
                messages.error(request, str(exc))
                return render(request, "web/send.html", {"form": form, "quote": quote})
            try:
                service.execute(transfer.id)
            except (service.KycRequired, service.LiquidityError) as exc:
                messages.error(request, str(exc))
                return redirect("web:dashboard")
            except service.ReviewRequired:
                messages.info(request, "Your transfer is held for a quick compliance review.")
            except Exception:  # noqa: BLE001 - marked FAILED inside execute
                messages.error(request, "Transfer failed. No funds were moved.")
            return redirect("web:transfer_detail", pk=transfer.id)

    return render(request, "web/send.html", {"form": form, "quote": quote})


def _resolve_web_recipient(request, cd):
    if cd.get("saved_recipient"):
        r = get_object_or_404(Recipient, id=cd["saved_recipient"], user=request.user)
        return r.card_token, r.last4, r.brand, cd.get("recipient_name") or r.name
    token, last4, brand = tokenize_card(cd["recipient_card_number"])
    return token, last4, brand, cd.get("recipient_name", "")


@login_required
def transfer_detail(request, pk):
    transfer = get_object_or_404(Transfer, pk=pk, user=request.user)
    return render(request, "web/transfer_detail.html", {"t": transfer})


@login_required
def statement_csv(request):
    """Download the signed-in user's transfer history as CSV."""
    import csv

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="ubique-statement.csv"'
    writer = csv.writer(response)
    writer.writerow([
        "id", "created", "status", "send_amount", "send_currency",
        "receive_amount", "receive_currency", "recipient_last4", "network",
    ])
    for t in request.user.transfers.all():
        writer.writerow([
            t.id, t.created_at.isoformat(), t.status, t.send_amount, t.send_currency,
            t.receive_amount, t.receive_currency, t.recipient_card_last4, t.network,
        ])
    return response


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


@staff_member_required
def ops_dashboard(request):
    """Operations dashboard: volume, status mix, revenue, treasury, recent."""
    from ubique.transfers.models import Transfer

    qs = Transfer.objects.all()
    total = qs.count()

    status_counts = {row["status"]: row["n"]
                     for row in qs.values("status").annotate(n=Count("id"))}
    status_rows = []
    for value, label in Status.choices:
        n = status_counts.get(value, 0)
        status_rows.append({
            "label": label, "n": n,
            "pct": round(100 * n / total) if total else 0,
            "value": value,
        })

    completed = qs.filter(status=Status.COMPLETED)
    volume = list(completed.values("send_currency").annotate(total=Sum("send_amount")))
    revenue = list(completed.values("send_currency").annotate(total=Sum("commission")))
    paid_out = list(completed.values("receive_currency").annotate(total=Sum("receive_amount")))

    ctx = {
        "total": total,
        "completed": status_counts.get(Status.COMPLETED, 0),
        "failed": status_counts.get(Status.FAILED, 0),
        "in_flight": total - status_counts.get(Status.COMPLETED, 0)
                     - status_counts.get(Status.FAILED, 0)
                     - status_counts.get(Status.REFUNDED, 0),
        "status_rows": status_rows,
        "volume": volume,
        "revenue": revenue,
        "paid_out": paid_out,
        "treasury": TreasuryBalance.objects.all(),
        "corridors_enabled": Corridor.objects.filter(enabled=True).count(),
        "corridors_total": Corridor.objects.count(),
        "recent": qs.select_related("user")[:12],
        "liquidity_enforced": settings.UBIQUE.get("LIQUIDITY_ENFORCED"),
        "awaiting_approval": qs.filter(status=Status.APPROVAL_PENDING)
                               .select_related("user", "onchain_approval"),
        "held_for_review": qs.filter(
            risk_decision="review", review_released=False, status=Status.QUOTED
        ).select_related("user"),
        "trial_balance": _trial_balance(),
    }
    return render(request, "web/ops.html", ctx)


def _trial_balance():
    from ubique.transfers.ledger import balances
    return [
        {"account": acct, "currency": ccy, "net": net}
        for (acct, ccy), net in sorted(balances().items())
    ]
