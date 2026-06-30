from django.contrib import admin

from .models import LedgerEntry, Transfer


class LedgerInline(admin.TabularInline):
    model = LedgerEntry
    extra = 0
    readonly_fields = ("account", "direction", "amount", "currency", "created_at")
    can_delete = False


@admin.register(Transfer)
class TransferAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "status", "send_amount", "send_currency",
                    "receive_currency", "network", "created_at")
    list_filter = ("status", "network", "send_currency")
    search_fields = ("user__phone", "idempotency_key", "payin_ref", "chain_tx")
    inlines = [LedgerInline]


@admin.register(LedgerEntry)
class LedgerEntryAdmin(admin.ModelAdmin):
    list_display = ("transfer", "account", "direction", "amount", "currency", "created_at")
    list_filter = ("direction", "account", "currency")
