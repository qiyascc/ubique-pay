from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models


class UserManager(BaseUserManager):
    def create_user(self, phone, password=None, **extra):
        if not phone:
            raise ValueError("Phone number is required.")
        user = self.model(phone=phone, **extra)
        user.set_password(password)  # unusable password for OTP-only users
        user.save(using=self._db)
        return user

    def create_superuser(self, phone, password, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("is_active", True)
        return self.create_user(phone, password, **extra)


class KycStatus(models.TextChoices):
    UNVERIFIED = "unverified", "Unverified"
    PENDING = "pending", "Pending review"
    VERIFIED = "verified", "Verified"
    REJECTED = "rejected", "Rejected"


class User(AbstractBaseUser, PermissionsMixin):
    phone = models.CharField(max_length=20, unique=True)
    telegram_id = models.BigIntegerField(unique=True, null=True, blank=True)
    telegram_username = models.CharField(max_length=64, blank=True)
    kyc_status = models.CharField(
        max_length=12, choices=KycStatus.choices, default=KycStatus.UNVERIFIED
    )
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    # May approve multisig treasury (on-chain) movements.
    is_treasury_signer = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD = "phone"
    REQUIRED_FIELDS = []

    objects = UserManager()

    def __str__(self):
        return self.phone

    @property
    def is_kyc_verified(self):
        return self.kyc_status == KycStatus.VERIFIED
