<h1 align="center">💸 Ubique Pay</h1>

<p align="center">
  <b>Send money to anyone, anywhere.</b><br>
  Card in → <b>USDT</b> on the cheapest network → card out. Lower fees than
  traditional remittance, settled in minutes.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Django-5.1-092E20?style=flat-square&logo=django&logoColor=white">
  <img src="https://img.shields.io/badge/DRF-API-a30000?style=flat-square">
  <img src="https://img.shields.io/badge/USDT-on_TON-26A5E4?style=flat-square&logo=tether&logoColor=white">
  <img src="https://img.shields.io/badge/security-hardened-5bffb4?style=flat-square&logo=letsencrypt&logoColor=black">
  <img src="https://img.shields.io/badge/license-MIT-blue?style=flat-square">
</p>

---

Ubique Pay is a cross-border money-movement platform. A sender funds a transfer
from their **card**, the value travels on-chain as **USDT** over the **cheapest
available network** (TON / Solana / TRON), and the recipient is paid out to
their **bank card** in local currency. The stablecoin leg is invisible to both
parties — the "stablecoin sandwich".

A **single Django project** serves both the server-rendered web UI and a REST
API (also consumable by a Telegram Mini App). Everything external — card
acquiring, on-chain transfer, card payout — sits behind swappable **provider
adapters**, so the whole flow runs end-to-end with mocks today and plugs into
Transak/Banxa, TON `tonutils` and Visa Direct/Mastercard Send in production.

## ✨ Highlights

- 🔁 **Cheapest-network routing** — a live quote engine prices the transfer and
  picks the lowest-fee network.
- 🧾 **Transparent quotes + double-entry ledger** — every fee shown before
  confirm; every money movement recorded.
- 🔌 **Adapter architecture** — swap providers per corridor via settings, no
  core changes.
- 🔐 **Security-hardened** — Argon2 hashing, HSTS, secure cookies, CSP,
  OTP rate-limiting, KYC gating, idempotent transfers. ([details](#-security))
- 🚀 **One-command install & deploy** — `install.py` + `deploy.py`
  (Gunicorn + systemd + Nginx).

See **[ARCHITECTURE.md](ARCHITECTURE.md)** for the full design and
**[COMPETITORS.md](COMPETITORS.md)** for how the economics compare to Western
Union, Wise, Remitly and MoneyGram.

## 🗺️ Flow

```
  Sender (Web · Telegram Mini App)
        │  card-in
        ▼
   ON-RAMP ──► CHAIN SENDER ──► PAYOUT ──►  Recipient card
   card→USDT   cheapest net.    USDT→fiat    (local currency)
        └──────── transparent quote + ledger + state machine ────────┘
```

State machine: `QUOTED → PAYIN_PENDING → PAYIN_SETTLED → ONCHAIN_SENT →
PAYOUT_PENDING → COMPLETED` (`→ FAILED → REFUNDED` on error).

## ⚡ Quickstart

```bash
python3 install.py                 # venv + deps + .env (fresh secret) + migrate
.venv/bin/python manage.py createsuperuser
.venv/bin/python manage.py runserver
```

Open **http://127.0.0.1:8000/** → log in with a phone number (the demo OTP is
shown on screen), verify identity (demo), add a card, and send money.

- Web UI: `/`
- REST API: `/api/v1/` · Admin: `/admin/`
- Telegram Mini App: `/app/`

## 📲 Telegram Mini App (full flow)

The Mini App (`/app/`) runs the **entire journey inside Telegram**:

1. **Sign-in** with real signed `initData` — HMAC-SHA256 validation against the
   bot token, per Telegram's spec (`ubique/accounts/telegram.py`).
2. **KYC** gate (`/api/v1/auth/kyc/start/`).
3. **Link a TON wallet** via TON Connect; add a card.
4. **Quote → confirm → result**, all calling the same REST API.

```bash
# https PUBLIC_BASE_URL is required (Telegram only opens https Web Apps)
TELEGRAM_BOT_TOKEN=... PUBLIC_BASE_URL=https://pay.example.com python bot.py
```

`/start` opens the Mini App; TON Connect manifest is at `/tonconnect-manifest.json`.

## 🪪 KYC — full Sumsub integration (pluggable)

`KYC_PROVIDER` selects the verifier: a **demo** provider (auto-verifies) by
default, or **Sumsub**, integrated end-to-end:

1. `POST /api/v1/auth/kyc/start/` → signed Sumsub API call mints an **access
   token** (`userId`, `levelName`, `ttlInSecs`).
2. The Mini App launches the **Sumsub WebSDK** (`snsWebSdk`) with that token;
   `POST /api/v1/auth/kyc/token/` refreshes it on expiry.
3. Sumsub calls `POST /api/v1/auth/kyc/webhook/`; the signature is verified
   (`X-Payload-Digest` with the algorithm from `X-Payload-Digest-Alg`,
   HMAC-SHA1/256/512) and `applicantReviewed` → `GREEN`/`RED` flips the user to
   verified/rejected.

Configure with `SUMSUB_APP_TOKEN`, `SUMSUB_SECRET_KEY`, `SUMSUB_LEVEL_NAME`,
`SUMSUB_WEBHOOK_SECRET`. Telegram **Passport** only *collects* encrypted
documents and still needs a verifier like Sumsub for liveness/AML, so Sumsub is
the engine; Passport can be added later as a document front-end.

## 🔗 Real on-chain transfers (TON, testnet-ready)

`TonChainSender` performs an **actual USDT-TON jetton transfer** via `tonutils`
2.1 (6 decimals, 0.05 TON gas). Spin up and inspect a treasury wallet:

```bash
python manage.py ton_wallet --create     # generate a TESTNET wallet + mnemonic
python manage.py ton_wallet              # derive the treasury address
```

Fund it via [@testgiver_ton_bot](https://t.me/testgiver_ton_bot), set
`TON_MNEMONIC` + `TON_TESTNET=1`, and transfers run on-chain. `TransakOnRampProvider`
(card → USDT) and `CheckoutPayoutProvider` (push-to-card) are likewise real and
credential-gated; the mocks stay the default so the project always runs.

## 🔌 REST API (`/api/v1/`)

| Method & path | Purpose |
|---------------|---------|
| `POST auth/request-otp/` · `verify-otp/` | Phone + OTP → auth token |
| `GET/POST wallets/cards/` · `crypto/` | Tokenized cards (PAN never stored) & crypto accounts |
| `POST quotes/` | Fee breakdown + cheapest-network routing |
| `GET/POST transfers/` · `GET transfers/{id}/` | Create/execute & inspect transfers (with ledger) |

## 💳 Recipients & payout

The recipient leg is complete end to end. Users save **recipients** (a name + a
**tokenized** card — the PAN is validated by Luhn, the brand + last 4 derived,
and only a token stored) or enter a fresh card at send time, in both the web app
(`/recipients/`) and the Telegram Mini App. The payout adapter
(`CheckoutPayoutProvider` / Visa Direct) is handed the recipient **token**, never
a raw PAN, and the result is confirmed by the `payout` webhook.

## 🌍 Corridors & treasury

Money only moves over **explicitly enabled corridors**. A `Corridor`
(`send → receive`) sets the allowed networks, min/max amounts and an optional
commission override; the quote engine rejects any pair without an enabled
corridor and routes over the cheapest of *that corridor's* networks. Manage them
in the Django admin (`/admin/`) — your ops dashboard.

A `TreasuryBalance` holds the **payout float** per currency. With
`UBIQUE_LIQUIDITY_ENFORCED=1`, a transfer is blocked unless its receive currency
has enough float, which is debited on payout — so you never promise a payout you
can't fund.

A staff-only **operations dashboard** at `/ops/` shows live volume, the
status mix, revenue, treasury floats, transfers **awaiting multisig approval**,
and recent activity.

### Multisig treasury

With `UBIQUE_MULTISIG_ENABLED=1`, any on-chain move at or above
`MULTISIG_MIN_USDT` is held in `APPROVAL_PENDING` and broadcast only after
`MULTISIG_THRESHOLD` **treasury signers** (`is_treasury_signer` users) approve
it via `POST /api/v1/transfers/{id}/approve/` — an M-of-N gate on the treasury.
The underlying TON wallet can additionally be an on-chain Multisig contract
(`TON_MULTISIG_ADDRESS`).

## 🏦 Payment-system internals

Built like a real rail, not a demo:

- **Asynchronous, webhook-driven** — providers confirm pay-ins/payouts via
  signed webhooks (`/api/v1/transfers/webhooks/{onramp,payout}/`). The same
  state-machine steps run inline for the synchronous mocks and via webhooks for
  real providers.
- **Webhook security** — every event is verified (`X-Ubique-Signature` =
  HMAC-SHA256 of the raw body) and **deduped** on `(provider, event id)`, so
  retries never double-process or double-spend.
- **Retry / dead-letter queue** — an event that can't be applied yet (e.g. it
  arrives before its transfer commits) is kept with the error recorded;
  `manage.py retry_webhooks` re-runs it, dead-lettering anything past
  `MAX_WEBHOOK_ATTEMPTS` (visible in the admin).
- **Reconciliation** — `python manage.py reconcile_transfers` polls providers
  and advances/fails any transfer stuck pending (a safety net for missed
  webhooks). Run both on a timer.
- **Pricing** — a **multi-source FX oracle** aggregates rate sources (median)
  and caches per pair (`FX_CACHE_TTL`); each corridor can override the on-ramp /
  payout / commission / spread rates and apply **amount-tiered** commission.
- **Risk & compliance** — KYC gate, per-user 24h **velocity limit**, and a
  sanctions **denylist** screen before any money moves.
- **Idempotency** — transfer creation, execution and every webhook are
  idempotent; the append-only ledger is the source of truth.

## 🔐 Security

Built secure-by-default — the most important part of a payments system:

- **Auth** — phone + OTP with per-hour send limits and per-code attempt limits
  (constant-time compare, single-use codes).
- **Passwords** — Argon2 hasher, 10-char minimum + validators.
- **Transport** — HSTS (1y, preload), SSL redirect, secure + HttpOnly + SameSite
  cookies, 30-minute sessions (all auto-enabled when `DEBUG=0`).
- **Headers** — CSP, `X-Frame-Options: DENY`, nosniff, referrer & permissions
  policy, COOP.
- **Money safety** — KYC gating before any transfer, **idempotent** creation &
  execution, an append-only **ledger**, and a strict state machine.
- **PCI** — card PANs never touch the server; only provider tokens + last 4.
- **Secrets** — everything via `.env`; `DJANGO_SECRET_KEY` is required when
  `DEBUG=0`.

## 🚀 Production deploy

```bash
# edit .env: DJANGO_DEBUG=0, DJANGO_SECRET_KEY, DJANGO_ALLOWED_HOSTS, DEPLOY_DOMAIN…
sudo python3 deploy.py             # Gunicorn (systemd socket+service) + Nginx
sudo certbot --nginx -d pay.example.com
```

`deploy.py` writes the systemd unit, socket and Nginx site, then enables and
starts everything. Gunicorn is configured in `gunicorn.conf.py`.

Or run the whole stack in containers:

```bash
cp .env.example .env        # set DJANGO_SECRET_KEY, UBIQUE_FIELD_KEYS, DB_*
docker compose up --build   # web + Postgres + maintenance worker
```

## 🛡️ Operations & security

- **API docs** — OpenAPI schema at `/api/v1/schema/`, Swagger UI at `/api/v1/docs/`.
- **Probes** — `/healthz` (liveness), `/readyz` (DB + cache readiness).
- **At-rest encryption** — card tokens are Fernet-encrypted (`UBIQUE_FIELD_KEYS`).
- **Outbound webhooks** — signed event delivery to integrations
  (`manage.py deliver_webhooks`).
- **AML/risk** — pluggable risk rules hold or block transfers; officers release
  via `POST /api/v1/transfers/<id>/release/`.
- **Ledger** — `manage.py check_ledger` prints the trial balance and asserts
  integrity; the `/ops/` dashboard shows it live.
- **Maintenance jobs** (run on a timer): `reconcile_transfers`,
  `retry_webhooks`, `deliver_webhooks`.
- **CI** — ruff + bandit + pip-audit + tests on every push.

See **[SECURITY.md](SECURITY.md)** for the full posture and OWASP API Top-10
mapping.

## 🧪 Tests

```bash
.venv/bin/python manage.py test
```

Covers quote routing, the full transfer flow, the ledger, idempotency, the KYC
gate, and an end-to-end API journey.

## ⚠️ Status

Runs end-to-end with **mock providers** — no real money moves. Real money
requires licensed providers (on-ramp/off-ramp, push-to-card) and money-transfer
licensing; this codebase is built to plug into them.

## License

MIT © Qiyas
