# Security

Ubique Pay moves money, so security is a first-class concern. This document
summarises the posture and how it maps to common frameworks. Report
vulnerabilities privately to **security@ubique.ubermensch.cc** — please do not
open public issues for security reports.

## Posture at a glance

**Authentication & sessions**
- Phone + OTP (rate-limited issuance & attempts, single-use, constant-time
  compare) and Telegram Mini App login via **real signed initData** (HMAC-SHA256,
  freshness-checked).
- API auth via tokens; web via sessions (HttpOnly, SameSite=Lax, secure in prod,
  30-minute expiry). Argon2 password hashing.

**Transport & headers**
- HSTS (1y, preload), SSL redirect, secure cookies — all auto-enabled when
  `DEBUG=0`. CSP, `X-Frame-Options: DENY`, nosniff, referrer & permissions
  policy, COOP via a dedicated middleware.

**Data protection**
- **PANs are never stored** — cards are tokenized (Luhn-checked; brand + last 4
  kept). Card tokens are **encrypted at rest** with Fernet (AES) field-level
  encryption; keys are rotation-capable (`UBIQUE_FIELD_KEYS`).
- Secrets come from the environment; nothing sensitive is committed.

**Money safety**
- Idempotent transfer creation (`Idempotency-Key` header or body) and idempotent
  webhook processing; an append-only **ledger** with trial-balance + integrity
  checks (`check_ledger`).
- Automatic **refunds/reversals** on failure; **multisig** approval for large
  on-chain moves; **liquidity** float checks; full **audit log** (immutable).

**AML / compliance**
- KYC gate (Sumsub) before any transfer; a pluggable **risk engine** that blocks
  or holds transfers for officer review; sanctions denylist; velocity limits.

**Webhooks**
- Inbound: HMAC-SHA256 signature verification, optional timestamp **replay
  window** (±5 min), and `(provider, event id)` **dedup**; failures retry and
  dead-letter.
- Outbound: signed `X-Ubique-Signature` over `"<timestamp>.<body>"` with retries
  and dead-lettering.

**Operations & supply chain**
- Health (`/healthz`) and readiness (`/readyz`) probes; request-id correlation
  and structured logging.
- CI runs **ruff**, **bandit** and **pip-audit** on every push; runs as a
  non-root container.

## OWASP API Security Top 10 mapping

| Risk | Mitigation |
|------|------------|
| API1 Broken Object-Level Auth (BOLA) | Every list/detail view is scoped to `request.user`; cross-user access is impossible by id. |
| API2 Broken Authentication | OTP rate-limiting, signed Telegram initData, token/session hardening. |
| API3 Property-Level Auth | Write-only secret fields (card numbers/tokens); serializers never echo PANs/tokens. |
| API4 Resource Consumption | DRF throttling (anon/user), OTP & velocity limits, pagination. |
| API5 Function-Level Auth | Admin-only release/approve endpoints; treasury-signer checks. |
| API7 SSRF / Injection | Parameterised ORM; outbound URLs are operator-configured; no template/SQL injection surface. |
| API8 Security Misconfiguration | `check --deploy` clean; security middleware always on; secrets from env. |
| API10 Unsafe Consumption | Provider responses validated; signed webhooks; timeouts on all outbound calls. |

## Key management

- `DJANGO_SECRET_KEY` and `UBIQUE_FIELD_KEYS` (Fernet) must be set in production.
  Field keys support rotation: prepend a new key, re-save records, then drop the
  old key.
- Webhook secrets (`*_WEBHOOK_SECRET`) and provider credentials are per-provider
  and should be rotated on a schedule.

## What is out of scope of this codebase

Licensing (MSB/VASP), provider contracts (acquiring, payout, on/off-ramp) and a
hardware-backed KMS are operational/legal requirements the software is built to
plug into, not replace.
