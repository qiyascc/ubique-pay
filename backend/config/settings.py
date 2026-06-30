"""Settings for the Ubique Pay backend.

Everything sensitive is read from the environment (see .env.example).
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-only-insecure-change-me")
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = [h for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "*").split(",") if h]

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
    "ubique.quotes",
    "ubique.transfers",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
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
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

CACHES = {
    "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}
}

AUTH_USER_MODEL = "accounts.User"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.TokenAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
}

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Ubique Pay configuration -------------------------------------------
UBIQUE = {
    # Provider adapters (swap the mocks for real adapters in production).
    "ONRAMP_PROVIDER": os.environ.get(
        "UBIQUE_ONRAMP", "ubique.providers.mock.MockOnRampProvider"
    ),
    "PAYOUT_PROVIDER": os.environ.get(
        "UBIQUE_PAYOUT", "ubique.providers.mock.MockPayoutProvider"
    ),
    "CHAIN_SENDER": os.environ.get(
        "UBIQUE_CHAIN_SENDER", "ubique.providers.mock.MockChainSender"
    ),
    "FX_ORACLE": os.environ.get(
        "UBIQUE_FX_ORACLE", "ubique.providers.mock.MockFxOracle"
    ),
    "NETWORK_FEE_ORACLE": os.environ.get(
        "UBIQUE_FEE_ORACLE", "ubique.providers.mock.MockNetworkFeeOracle"
    ),
    # Networks the router may choose from, cheapest wins.
    "SUPPORTED_NETWORKS": ["TON", "SOLANA", "TRON"],
    # Ubique's own commission (fraction of send amount).
    "COMMISSION_RATE": float(os.environ.get("UBIQUE_COMMISSION_RATE", "0.005")),
    # FX spread applied on top of the mid-market rate.
    "FX_SPREAD": float(os.environ.get("UBIQUE_FX_SPREAD", "0.005")),
    # Per-transfer limits (in send currency minor→major units).
    "MIN_SEND": float(os.environ.get("UBIQUE_MIN_SEND", "20")),
    "MAX_SEND": float(os.environ.get("UBIQUE_MAX_SEND", "10000")),
}
