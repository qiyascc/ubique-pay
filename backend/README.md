# Ubique Pay — Backend

Django + DRF backend for the cross-border card→USDT→card flow described in
[`../ARCHITECTURE.md`](../ARCHITECTURE.md). It runs end-to-end with **mock
providers** so you can exercise the whole sender→recipient journey locally; real
providers (Transak/Banxa on-ramp, TON `tonutils`, Visa Direct/Mastercard Send
payout) plug in behind the adapter interfaces.

## Run

```bash
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py runserver
```

## API (all under `/api/v1/`)

| Method & path | Purpose |
|---------------|---------|
| `POST auth/request-otp/` | Send a one-time code (returned in `debug_code` when DEBUG) |
| `POST auth/verify-otp/` | Verify code → returns an auth token |
| `GET  auth/me/` | Current user + KYC status |
| `GET/POST wallets/cards/` | List / add a tokenized card (PAN never stored) |
| `GET/POST wallets/crypto/` | List / add a crypto account (e.g. TON address) |
| `POST quotes/` | Fee breakdown + cheapest-network routing |
| `GET/POST transfers/` | List / create (and execute) a transfer |
| `GET transfers/{id}/` | Transfer detail incl. ledger |

Authenticate with `Authorization: Token <token>`.

## How a transfer works

1. `quotes/` prices the transfer and the **router picks the cheapest network**
   (`NetworkFeeOracle` over `SUPPORTED_NETWORKS`).
2. `POST transfers/` freezes that quote and runs the state machine:
   `QUOTED → PAYIN_PENDING → PAYIN_SETTLED → ONCHAIN_SENT → PAYOUT_PENDING →
   COMPLETED`, writing a double-entry **ledger** at each leg. KYC-unverified
   senders are blocked; creation is idempotent on `idempotency_key`.

## Swapping in real providers

Set the `UBIQUE_*` env vars to a dotted path of a real adapter (see
`ubique/providers/real.py` for documented stubs) — no core code changes needed.

## Tests

```bash
python manage.py test
```
