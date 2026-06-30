from django.contrib import admin

from .models import (
    LedgerEntry,
    OnchainApproval,
    OutboundDelivery,
    Transfer,
    WebhookEndpoint,
    WebhookEvent,
)


@admin.register(WebhookEndpoint)
class WebhookEndpointAdmin(admin.ModelAdmin):
    list_display = ("url", "events", "enabled", "created_at")
    list_filter = ("enabled",)


@admin.register(OutboundDelivery)
class OutboundDeliveryAdmin(admin.ModelAdmin):
    list_display = ("event_type", "endpoint", "status", "attempts",
                    "response_code", "next_attempt_at")
    list_filter = ("status", "event_type")
    readonly_fields = ("endpoint", "event_type", "payload", "status", "attempts",
                       "next_attempt_at", "response_code", "error", "created_at")


@admin.register(OnchainApproval)
class OnchainApprovalAdmin(admin.ModelAdmin):
    list_display = ("transfer", "approval_count", "threshold", "is_satisfied", "created_at")
    filter_horizontal = ("approvers",)


class LedgerInline(admin.TabularInline):
    model = LedgerEntry
    extra = 0
    readonly_fields = ("account", "direction", "amount", "currency", "created_at")
    can_delete = False


@admin.action(description="Refund selected failed transfers")
def refund_failed(modeladmin, request, queryset):
    from . import service
    n = 0
    for transfer in queryset.filter(status="failed"):
        service.refund(transfer)
        n += 1
    modeladmin.message_user(request, f"Refunded {n} transfer(s).")


@admin.register(Transfer)
class TransferAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "status", "send_amount", "send_currency",
                    "receive_currency", "network", "created_at")
    list_filter = ("status", "network", "send_currency")
    search_fields = ("user__phone", "idempotency_key", "payin_ref", "chain_tx")
    inlines = [LedgerInline]
    actions = [refund_failed]


@admin.register(LedgerEntry)
class LedgerEntryAdmin(admin.ModelAdmin):
    list_display = ("transfer", "account", "direction", "amount", "currency", "created_at")
    list_filter = ("direction", "account", "currency")


@admin.register(WebhookEvent)
class WebhookEventAdmin(admin.ModelAdmin):
    list_display = ("provider", "event_type", "external_id", "processed",
                    "attempts", "received_at")
    list_filter = ("provider", "processed")
    search_fields = ("external_id",)
    readonly_fields = ("provider", "external_id", "event_type", "payload",
                       "attempts", "error", "received_at")
