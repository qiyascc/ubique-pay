from django.contrib import admin

from .models import User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("phone", "kyc_status", "is_active", "date_joined")
    list_filter = ("kyc_status", "is_active")
    search_fields = ("phone",)
