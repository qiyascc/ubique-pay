"""Tiny helper to write audit-log entries from anywhere.

    from ubique.audit.log import log
    log("transfer.completed", target=f"transfer:{t.id}", amount=str(t.send_amount))
"""


def log(action, *, actor=None, target="", ip=None, **metadata):
    from .models import AuditLog

    authed = bool(actor) and getattr(actor, "is_authenticated", False)
    AuditLog.objects.create(
        actor=actor if authed else None,
        actor_label=str(actor) if actor else "system",
        action=action,
        target=str(target) if target else "",
        ip=ip or None,
        metadata={k: v for k, v in metadata.items() if v is not None},
    )
