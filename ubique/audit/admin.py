from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """Read-only — the audit trail is immutable."""

    list_display = ("created_at", "actor_label", "action", "target", "ip")
    list_filter = ("action",)
    search_fields = ("actor_label", "action", "target", "ip")
    readonly_fields = ("actor", "actor_label", "action", "target", "ip",
                       "metadata", "created_at")
    date_hierarchy = "created_at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
