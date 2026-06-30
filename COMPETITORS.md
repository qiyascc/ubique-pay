# Competitive Analysis

How Ubique Pay's economics compare to mainstream remittance services. Figures
are 2026 public ranges; real cost always depends on corridor, amount and
payment method.

## All-in cost (fee + FX markup)

| Provider | Up-front fee | FX markup | Typical all-in (card) | Speed |
|----------|-------------|-----------|-----------------------|-------|
| **Ubique Pay** | 0 | 0.5% spread | **~1.5–4%** | minutes |
| Western Union | $0–25+ | 2–4% | 4–6%+ | minutes–days |
| MoneyGram | $1.99–11.99 | 1–3% | 3–6% | minutes–days |
| Remitly | varies | 1–3.7% | 2–5% | minutes–days |
| Wise | ~0.4–1% | mid-market (0%) | ~1–1.5% | minutes–hours |
| _Global average (World Bank)_ | — | — | **~6.5%** | days |

> Ubique's edge is the **rail**: USDT moves on-chain for a fraction of a cent
> (TON ~$0.003–0.04, Solana <$0.001) instead of through correspondent banks.
> The cost that remains is card acquiring (pay-in) and push-to-card (pay-out),
> which is why paying in by bank/Apple Pay instead of card lands near the low
> end of the range.

## Worked example — send 200 USD → AZN

| Provider | Recipient receives (approx) | Effective cost |
|----------|-----------------------------|----------------|
| **Ubique Pay** (card-in) | **326.5 AZN** | ~4% |
| **Ubique Pay** (bank-in) | ~333 AZN | ~2% |
| Western Union (card) | ~318–326 AZN | 4–6% |
| Wise | ~335 AZN | ~1.3% |

_Ubique figures are produced by the live quote engine in this repo
(`ubique/quotes/engine.py`); the network is chosen dynamically as the cheapest
of the configured set._

## Where Ubique wins / loses

**Wins**
- Near-zero settlement cost on-chain vs correspondent banking.
- Fully transparent quote — every fee shown before confirm, no hidden FX.
- Telegram-native (TON Connect / TON Pay) — reach users where they already are.
- 24/7 settlement in minutes.

**Loses / honest caveats**
- Card-in + push-to-card fees (acquiring ~2%, payout ~1%) are unavoidable
  third-party costs; Wise undercuts on pure bank-to-bank.
- Requires KYC/AML and money-transfer licensing — a regulatory burden incumbents
  have already absorbed.
- Liquidity / FX spread on exotic corridors can erode the on-chain savings.

## Strategy

Lead with **card-to-card to under-served corridors** (where incumbents charge
5–8%), default the pay-in to the cheapest method available, and pin settlement
to **TON** for Telegram users (`UBIQUE_NETWORKS=TON`) to keep the rail both cheap
and native to the channel.

### Sources
- World Bank / industry: global remittance average ≈ 6.5%.
- Western Union, MoneyGram, Remitly, Wise published 2026 fee ranges.
