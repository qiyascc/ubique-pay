"""Settings for Ubique Pay.

A single Django project: it serves both the server-rendered web UI and the
REST API. Everything sensitive is read from the environment / a .env file
(see .env.example). Secure-by-default: DEBUG is off and security headers are on
unless explicitly relaxed for local development.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env (if present) before reading any settings.
load_dotenv(BASE_DIR / ".env")


def env_bool(name, default="0"):
    return os.environ.get(name, default).strip().lower() in {"1", "true", "yes", "on"}


def env_list(name, default=""):
    return [v.strip() for v in os.environ.get(name, default).split(",") if v.strip()]


# --- Core -----------------------------------------------------------------
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
DEBUG = env_bool("DJANGO_DEBUG", "0")
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost")

if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "django-insecure-dev-only-key-do-not-use-in-production"
    else:
        raise RuntimeError("DJANGO_SECRET_KEY must be set when DEBUG is off.")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework.authtoken",
    "ubique.accounts",
    "ubique.wallets",
    "ubique.corridors",
    "ubique.quotes",
    "ubique.transfers",
    "ubique.audit",
    "ubique.web",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "ubique.common.security.SecurityHeadersMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": [
            "django.template.context_processors.debug",
            "django.template.context_processors.request",
            "django.contrib.auth.context_processors.auth",
            "django.contrib.messages.context_processors.messages",
        ]},
    },
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.environ.get("DJANGO_DB_NAME", BASE_DIR / "db.sqlite3"),
    }
}
if os.environ.get("DB_NAME"):  # opt-in PostgreSQL for production
    DATABASES["default"] = {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ["DB_NAME"],
        "USER": os.environ.get("DB_USER", ""),
        "PASSWORD": os.environ.get("DB_PASSWORD", ""),
        "HOST": os.environ.get("DB_HOST", "localhost"),
        "PORT": os.environ.get("DB_PORT", "5432"),
    }

CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

AUTH_USER_MODEL = "accounts.User"

# Argon2 first — strongest available password hasher.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
     "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "web:login"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.TokenAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {"anon": "30/min", "user": "300/min"},
}

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"] if (BASE_DIR / "static").exists() else []
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Security hardening ---------------------------------------------------
# Session & CSRF cookies
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_AGE = 60 * 30  # 30 minutes
CSRF_COOKIE_HTTPONLY = False  # JS needs to read the token for fetch()
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

# Headers always on
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
X_FRAME_OPTIONS = "DENY"

# HTTPS-only settings, enabled when not in DEBUG
if not DEBUG:
    SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", "1")
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

# Content-Security-Policy emitted by SecurityHeadersMiddleware.
CONTENT_SECURITY_POLICY = os.environ.get(
    "DJANGO_CSP",
    "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
    "script-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'",
)

# --- KYC ------------------------------------------------------------------
# Demo provider auto-verifies; switch to Sumsub in production.
KYC_PROVIDER = os.environ.get("KYC_PROVIDER", "ubique.accounts.kyc.DemoKycProvider")
SUMSUB_WEBHOOK_SECRET = os.environ.get("SUMSUB_WEBHOOK_SECRET", "")

# --- Telegram Mini App ---------------------------------------------------
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_BOT_USERNAME = os.environ.get("TELEGRAM_BOT_USERNAME", "")
# Public base URL of this app, used in the TON Connect manifest / Mini App.
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "http://localhost:8000")

# --- Ubique Pay configuration --------------------------------------------
UBIQUE = {
    "ONRAMP_PROVIDER": os.environ.get("UBIQUE_ONRAMP", "ubique.providers.mock.MockOnRampProvider"),
    "PAYOUT_PROVIDER": os.environ.get("UBIQUE_PAYOUT", "ubique.providers.mock.MockPayoutProvider"),
    "CHAIN_SENDER": os.environ.get("UBIQUE_CHAIN_SENDER", "ubique.providers.mock.MockChainSender"),
    "FX_ORACLE": os.environ.get("UBIQUE_FX_ORACLE", "ubique.providers.fx.CachingMultiSourceFxOracle"),
    "NETWORK_FEE_ORACLE": os.environ.get("UBIQUE_FEE_ORACLE", "ubique.providers.mock.MockNetworkFeeOracle"),
    # TON-first (the Telegram-native rail with deep USDT liquidity). The router
    # still picks the cheapest of whatever is listed — add SOLANA/TRON per
    # corridor to widen routing.
    "SUPPORTED_NETWORKS": env_list("UBIQUE_NETWORKS", "TON,TRON"),
    "COMMISSION_RATE": float(os.environ.get("UBIQUE_COMMISSION_RATE", "0.005")),
    "FX_SPREAD": float(os.environ.get("UBIQUE_FX_SPREAD", "0.005")),
    # Third-party rail costs (configurable instead of hard-coded in the engine).
    "ONRAMP_FEE_RATE": float(os.environ.get("UBIQUE_ONRAMP_FEE_RATE", "0.02")),
    "PAYOUT_FEE_RATE": float(os.environ.get("UBIQUE_PAYOUT_FEE_RATE", "0.01")),
    "MIN_SEND": float(os.environ.get("UBIQUE_MIN_SEND", "20")),
    "MAX_SEND": float(os.environ.get("UBIQUE_MAX_SEND", "10000")),
    "MAX_DAILY": float(os.environ.get("UBIQUE_MAX_DAILY", "20000")),
    # Block payouts when the receive-currency float is insufficient.
    "LIQUIDITY_ENFORCED": env_bool("UBIQUE_LIQUIDITY_ENFORCED", "0"),
    # Comma-separated phones / card last4 to block (sanctions/compliance demo).
    "DENYLIST": env_list("UBIQUE_DENYLIST"),
    # OTP anti-abuse
    "OTP_MAX_PER_HOUR": int(os.environ.get("UBIQUE_OTP_MAX_PER_HOUR", "5")),
    "OTP_MAX_ATTEMPTS": int(os.environ.get("UBIQUE_OTP_MAX_ATTEMPTS", "5")),
    # Webhook signing secrets (per provider).
    "ONRAMP_WEBHOOK_SECRET": os.environ.get("ONRAMP_WEBHOOK_SECRET", ""),
    "PAYOUT_WEBHOOK_SECRET": os.environ.get("PAYOUT_WEBHOOK_SECRET", ""),
    "MAX_WEBHOOK_ATTEMPTS": int(os.environ.get("UBIQUE_MAX_WEBHOOK_ATTEMPTS", "5")),
    # Multisig treasury: on-chain moves at/above MULTISIG_MIN_USDT need
    # MULTISIG_THRESHOLD approvals from treasury signers before broadcasting.
    "MULTISIG_ENABLED": env_bool("UBIQUE_MULTISIG_ENABLED", "0"),
    "MULTISIG_THRESHOLD": int(os.environ.get("UBIQUE_MULTISIG_THRESHOLD", "2")),
    "MULTISIG_MIN_USDT": float(os.environ.get("UBIQUE_MULTISIG_MIN_USDT", "1000")),
    # Optional on-chain TON multisig contract address for the treasury wallet.
    "TON_MULTISIG_ADDRESS": os.environ.get("TON_MULTISIG_ADDRESS", ""),
    # FX: multiple sources aggregated (median) and cached.
    "FX_SOURCES": env_list(
        "UBIQUE_FX_SOURCES",
        "ubique.providers.fx.SourceA,ubique.providers.fx.SourceB",
    ),
    "FX_CACHE_TTL": int(os.environ.get("UBIQUE_FX_CACHE_TTL", "60")),
}
