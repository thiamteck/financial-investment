---
name: klse-valuation
description: >
  Analyse any Bursa Malaysia (KLSE) listed company and produce a structured fair value report with
  investment stance, entry range, stop-loss, and review triggers. Use this whenever the user mentions
  a Malaysian stock, a Bursa ticker (e.g. 1155.KL, 5168.KL), a KLSE company name (e.g. Maybank,
  Public Bank, IHH, Top Glove, Gamuda, Tenaga, Petronas Chemicals), or asks any of: "is this stock
  worth buying", "what is the fair value of X", "analyse this Bursa stock", "should I buy/sell X",
  "target price for X", "is X undervalued", "review my Malaysian stock holding". Also triggers when
  the user pastes a .KL ticker or describes a company and asks for a valuation opinion. Do not wait
  for the user to say "run klse-valuation" — if they are asking about the value or investment merit
  of any Bursa-listed company, invoke this skill immediately.
---

# KLSE Valuation Skill

## Purpose
Analyse a Bursa Malaysia listed company and produce a structured fair value report with investment
stance. Uses Python stdlib only — no third-party libraries required.

## Input
Stock ticker (`XXXX.KL`) or company name (e.g. "Maybank", "Pavilion REIT").

---

## Quick Start

**Step 1 — Resolve the ticker (if only a company name is given):**

Use WebSearch to find the Bursa stock code before running the script:
```
WebSearch: "{company name} Bursa Malaysia stock code ticker"
```
Extract the 4-digit code from the result (e.g. `5212` for Pavilion REIT) and append `.KL`.

**Step 2 — Run the analysis script:**

```
python scripts/analyse.py <TICKER.KL>
```

Examples:
```
python scripts/analyse.py 1155.KL
python scripts/analyse.py 5212.KL
python scripts/analyse.py 5168.KL
```

The report is printed to stdout — pipe to a file if needed:
```
python scripts/analyse.py 1155.KL > report.txt
```

---

## Scripts

| File | Purpose |
|---|---|
| `scripts/fetch.py` | HTTP session, cookie/crumb auth for Yahoo Finance, `yf_get()`, `http_get()` |
| `scripts/analyse.py` | Full analysis pipeline — Steps 0–11, valuation models, report output |

Both scripts use Python stdlib only (`urllib`, `json`, `ssl`, `http.cookiejar`, `re`).

---

## Execution Flow (what `analyse.py` does)

```
Step 0  →  Resolve ticker from name if needed — WebSearch first, then script
Step 1  →  Fetch financial data (Yahoo Finance JSON API — quoteSummary + chart)
Step 2  →  Fetch analyst & peer data (KLSE Screener)
Step 3  →  Fetch analyst calls & dividend history (i3investor)
Step 4  →  Fetch Bursa announcements (QR, insider trades, substantial shareholders)
Step 5  →  Detect sector & company type → select valuation model weights
Step 6  →  Liquidity flag (avg daily value < RM500k = ILLIQUID)
Step 7  →  Financial health check (ROE, FCF, margins, D/E, balance sheet)
Step 8  →  Run valuation models (DCF, P/E, P/B, EV/EBITDA, DDM)
Step 9  →  Fetch KLCI benchmark for P/E and P/B market context
Step 10 →  Catalyst & risk assessment (manual — from Bursa announcements and news)
Step 11 →  Print structured report
```

If any data source fails, the script notes the gap and continues — it never aborts.

---

## Data Sources

| Source | What it provides | URL pattern |
|---|---|---|
| Yahoo Finance | Price, ratios, financials, 5yr history | `query1.finance.yahoo.com/v10/finance/quoteSummary/{ticker}` |
| KLSE Screener | Analyst consensus, sector, peers | `klsescreener.com/v2/stocks/view/{code}` |
| i3investor | Individual analyst calls, dividend history | `klse.i3investor.com/web/entitle/list.jsp?code={code}` |
| Bursa Malaysia | QR results, insider trades, Form 29A/29B | `bursamalaysia.com/market_information/announcements/...` |

**Yahoo Finance auth note:** Yahoo Finance requires a session cookie + crumb token since mid-2024.
`fetch.py` handles this automatically via `init_session()` — do not call Yahoo Finance URLs
directly without going through `yf_get()`.

---

## Valuation Model Weights by Company Type

| Company Type | DCF | P/E | P/B | EV/EBITDA | DDM |
|---|---|---|---|---|---|
| Bank | 10% | 20% | 40% | 0% | 30% |
| REIT | 10% | 0% | 30% | 0% | 60% |
| Plantation | 30% | 20% | 10% | 40% | 0% |
| Construction | 20% | 20% | 10% | 50% | 0% |
| Utility/Telco | 30% | 20% | 10% | 10% | 30% |
| Property | 20% | 20% | 40% | 20% | 0% |
| Manufacturing | 35% | 30% | 10% | 25% | 0% |
| General | 25% | 25% | 20% | 20% | 10% |

If a model is skipped (missing data), the script renormalises remaining weights to 100%.

**Bank DCF note:** FCF and operating CF are distorted for banks (loan book movements dominate
cash flow). The script substitutes `net_income × (1 − dividend_payout)` as a retained-earnings
proxy instead. This substitution is flagged in the report.

---

## Stance Rules

| Condition | Stance |
|---|---|
| Price ≥ 15–20% below weighted fair value | **BUY** |
| Price within ~10% of fair value | **HOLD** |
| Price > 10% above fair value | **SELL** |
| Fundamental red flags regardless of price | **AVOID** |

---

## Manual Steps (not automated)

The script outputs placeholder text for these — complete them after running:

- **Analyst consensus target price** — read from KLSE Screener (HTML parsing is fragile; verify manually)
- **Bank-specific metrics** — NIM, GIL ratio, CET1: check latest Bursa QR announcement
- **Catalysts and risks** — review Bursa announcements (Step 10) and recent news
- **DPS growth rate** — script defaults to 2%; verify on i3investor dividend history for DDM accuracy
- **Warrant/ESOS dilution** — if warrants > 5% of shares, adjust share count manually and rerun

---

## Margin of Safety Rule

Flag as BUY only if current price is at least **15–20% below** weighted fair value.
This accounts for model estimation error, data lag, and Malaysia-specific liquidity risk.

---

## Standing Rules

- All monetary values in RM unless stated otherwise
- ACE Market stocks: apply 20–30% additional discount to fair value vs equivalent Main Market stock
- WACC default 10%; script adjusts: −1% for beta < 0.7 (blue chip), +1% for beta > 1.3 (high risk)
- Never substitute zeros or averages for missing data — every gap is flagged in DATA GAPS section
