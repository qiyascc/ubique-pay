from django.db import migrations

# Sensible default corridors: send from USD/EUR to AZN/TRY over TON/TRON.
SEED = [
    ("USD", "AZN"),
    ("USD", "TRY"),
    ("EUR", "AZN"),
    ("EUR", "TRY"),
]


def seed(apps, schema_editor):
    Corridor = apps.get_model("corridors", "Corridor")
    for send, receive in SEED:
        Corridor.objects.get_or_create(
            send_currency=send, receive_currency=receive,
            defaults={"networks": "TON,TRON", "enabled": True},
        )


def unseed(apps, schema_editor):
    Corridor = apps.get_model("corridors", "Corridor")
    Corridor.objects.filter(
        send_currency__in=["USD", "EUR"], receive_currency__in=["AZN", "TRY"]
    ).delete()


class Migration(migrations.Migration):
    dependencies = [("corridors", "0001_initial")]
    operations = [migrations.RunPython(seed, unseed)]
