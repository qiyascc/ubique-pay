from django.contrib import admin

from .models import Corridor, TreasuryBalance


@admin.register(Corridor)
class CorridorAdmin(admin.ModelAdmin):
    list_display = ("send_currency", "receive_currency", "networks",
                    "min_amount", "max_amount", "commission_rate", "enabled")
    list_filter = ("enabled", "send_currency", "receive_currency")
    list_editable = ("enabled",)


@admin.register(TreasuryBalance)
class TreasuryBalanceAdmin(admin.ModelAdmin):
    list_display = ("currency", "available", "updated_at")
