"""Loads the configured provider adapters from settings."""

from functools import cache

from django.conf import settings
from django.utils.module_loading import import_string


@cache
def _load(key):
    return import_string(settings.UBIQUE[key])()


def onramp():
    return _load("ONRAMP_PROVIDER")


def chain_sender():
    return _load("CHAIN_SENDER")


def payout():
    return _load("PAYOUT_PROVIDER")


def fx_oracle():
    return _load("FX_ORACLE")


def network_fee_oracle():
    return _load("NETWORK_FEE_ORACLE")
