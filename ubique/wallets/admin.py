from django.contrib import admin

from .models import CryptoAccount, PaymentCard, Recipient


@admin.register(Recipient)
class RecipientAdmin(admin.ModelAdmin):
    list_display = ("user", "name", "brand", "last4", "created_at")
    search_fields = ("user__phone", "name", "last4")


@admin.register(PaymentCard)
class PaymentCardAdmin(admin.ModelAdmin):
    list_display = ("user", "brand", "last4", "is_default", "created_at")
    search_fields = ("user__phone", "last4")


@admin.register(CryptoAccount)
class CryptoAccountAdmin(admin.ModelAdmin):
    list_display = ("user", "network", "address", "created_at")
    search_fields = ("user__phone", "address")
