from django.conf import settings
from django.db import models


class AuditLog(models.Model):
    """Append-only record of who did what, when. Never updated or deleted."""

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="audit_logs",
    )
    actor_label = models.CharField(max_length=64, default="system")
    action = models.CharField(max_length=64, db_index=True)
    target = models.CharField(max_length=128, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.created_at:%Y-%m-%d %H:%M} {self.actor_label} {self.action} {self.target}"
