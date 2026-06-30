# Ubique Pay — Architecture

Cross-border money movement: a sender funds a transfer from their card, the
value travels on-chain as **USDT** over the **cheapest available network**, and
the recipient is paid out to their **bank card** in their local currency. The
stablecoin leg is invisible to both parties (the "stablecoin sandwich").

```
  Sender (Web or Telegram Mini App)
        │  card-in (pay-in)
        ▼
  ┌───────────────┐   USDT on-chain    ┌───────────────┐
  │  ON-RAMP      │ ─────────────────► │  CHAIN SENDER │
  │  card → USDT  │   cheapest network │  USDT transfer│
  └───────────────┘                    └───────┬───────┘
                                               │
                                       ┌───────▼───────┐   card-out (payout)
                                       │   OFF-RAMP /  │ ─────────────────►  Recipient card
                                       │   PAYOUT      │   local currency
                                       └───────────────┘
```

---

## 1. Channels

Both channels talk to the **same REST API**; no business logic lives in the
clients.

- **Web** — the existing React/Vite app (`/src`).
- **Telegram Mini App** — TON Connect / TON Pay (launched Feb 2026) gives
  wallet-less, one-tap USDT inside Telegram. The bot opens the same Mini App and
  authenticates the user via Telegram `initData`.

## 2. The money rail (researched, real components)

| Leg | What happens | Real providers | Cost (typical) |
|-----|--------------|----------------|----------------|
| **Pay-in** | Charge sender's card, receive USDT to our treasury wallet | Transak / Banxa on-ramp (crypto acquiring) | 0.5–5.5% |
| **On-chain** | Move USDT to the payout pool on the **cheapest** network | `tonutils` (TON), Solana/TRON SDKs | TON ~$0.003–0.04; SOL <$0.001; TRON $0–4 |
| **Pay-out** | Push funds to recipient's card in local fiat | Visa Direct (OCT), Mastercard Send, TabaPay, Checkout.com; or Banxa off-ramp | 1–3% |

### Why USDT on TON
- USDT-TON jetton uses **6 decimals**; a transfer costs a flat **~0.05 TON** of
  gas (paid in TON, not USDT) — a fraction of a cent.
- A recipient address receiving USDT for the first time needs its **jetton
  wallet contract** deployed (a few cents of TON), which our `ChainSender`
  funds automatically.
- The network is **not hardcoded**: a `NetworkFeeOracle` quotes TON / Solana /
  TRON live and the router picks the cheapest that both legs support.

## 3. Backend services (`backend/`)

Django + DRF. Every external dependency is hidden behind an **adapter** so the
core logic is testable with mocks and providers can be swapped per corridor.

```
config/                 settings (env-driven), urls
ubique/
  accounts/   phone + OTP auth, Telegram initData login
  wallets/    PaymentCard (tokenized, never stores PAN), CryptoAccount
  quotes/     FxOracle, NetworkFeeOracle, QuoteEngine (cheapest-network routing)
  transfers/  Transfer model, state machine, double-entry Ledger, webhooks
  providers/  adapter interfaces + mock + (stub) real adapters, registry
  common/     money helpers, idempotency
```

### Quote engine
Given `(send_amount, send_ccy, receive_ccy)` it returns a breakdown:

```
send_amount
  − on_ramp_fee
  − network_fee        (min across supported networks → chosen_network)
  − payout_fee
  − ubique_commission
= recipient_receives   (converted at FX mid + spread)
```

The chosen network and a frozen quote id are stored so the executed transfer
matches the price shown.

### Transfer state machine
Idempotent, advanced by provider webhooks; every money movement writes a
double-entry `Ledger` row.

```
CREATED → QUOTED → PAYIN_PENDING → PAYIN_SETTLED
        → ONCHAIN_SENT → PAYOUT_PENDING → COMPLETED
                                        ↘ FAILED → REFUNDED
```

### Provider adapter interfaces
- `OnRampProvider.create_payin()/get_status()` — card → USDT
- `ChainSender.send()/get_status()` — USDT transfer on a given network
- `PayoutProvider.create_payout()/get_status()` — USDT/fiat → recipient card
- `FxOracle.rate()` and `NetworkFeeOracle.fee()`

Mock implementations make the whole flow runnable end-to-end without real
credentials. Real adapters (Transak, Visa Direct, TON `tonutils`) are provided
as documented stubs to be wired once provider accounts exist.

## 4. Security & compliance (must-have before real money)

This is a regulated money-services activity. The **software** here is built to
plug into licensed providers; the **licensing and provider contracts are not**.

- **KYC/AML** — onboarding (ID + selfie) is delegated to the on-ramp/KYC vendor;
  the backend stores only verification status, never raw documents.
- **PCI** — card PANs never touch our servers; we store provider **tokens** and
  the last 4 digits only.
- **Sanctions/limits** — per-user and per-transfer limits, sanction screening
  hooks, and full audit via the ledger.
- **Idempotency** — every state-changing call takes an idempotency key so retried
  webhooks/clients never double-spend.

## 5. Running

See [`README.md`](README.md). The mock providers let you run the full
sender → recipient flow locally with `python install.py` + `manage.py runserver`
and the test suite (`python manage.py test`).
