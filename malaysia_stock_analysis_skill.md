# Skill: Malaysia Listed Company Fair Value Analysis

## Purpose
Analyse a Bursa Malaysia listed company and produce a structured fair value report with investment stance. Executable in Claude web and Claude desktop using Python stdlib only (no third-party libraries).

---

## Input
Stock ticker (`XXXX.KL`) or company name. If company name is given, execute Step 0 first.

---

## Execution Flow

```
Step 0  →  Resolve ticker (if name given)
Step 1  →  Fetch financial data (Yahoo Finance JSON API)
Step 2  →  Fetch analyst & peer data (KLSE Screener)
Step 3  →  Fetch analyst calls & dividend history (i3investor)
Step 4  →  Fetch Bursa announcements (insider trades, substantial shareholders)
Step 5  →  Detect sector & company type
Step 6  →  Liquidity flag check
Step 7  →  Financial health check
Step 8  →  Run valuation models (sector-appropriate)
Step 9  →  Fetch benchmark context (KLCI)
Step 10 →  Catalyst & risk assessment
Step 11 →  Produce output report
```

---

## Python Helper — HTTP Fetch (stdlib only)

Use this base fetch function throughout. All scripts use only `urllib`, `json`, `html.parser` from Python stdlib.

```python
import urllib.request
import json
import ssl

def http_get(url, headers=None):
    default_headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    if headers:
        default_headers.update(headers)
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, headers=default_headers)
    with urllib.request.urlopen(req, context=ctx, timeout=15) as r:
        return r.read().decode("utf-8")
```

If a fetch fails (HTTP 429, timeout, empty response), note the data gap explicitly in the report and continue with available data. Do not halt analysis.

---

## Step 0 — Resolve Ticker (if company name given)

```python
name = "maybank"  # replace with input
url = f"https://www.klsescreener.com/v2/screener/stock?keyword={urllib.parse.quote(name)}"
html = http_get(url)
# Parse first result's ticker code from HTML table
# KLSE Screener search returns rows with stock code and name
# Extract 4-digit code (e.g. 1155), append ".KL" → "1155.KL"
```

Alternatively, search: `https://finance.yahoo.com/lookup?s={name}+KL` and extract the `.KL` ticker from results.

---

## Step 1 — Fetch Financial Data (Yahoo Finance JSON API)

Yahoo Finance exposes JSON endpoints — no Python library required, just `urllib`.

### 1a. Quote Summary (ratios, margins, cash flow)

```python
ticker = "1155.KL"
modules = ",".join([
    "summaryDetail",          # price, market cap, P/E, dividend yield, beta, 52w range, avg volume
    "financialData",          # revenue, margins, ROE, debt/equity, FCF, operating CF, EBITDA
    "defaultKeyStatistics",   # EPS, book value, P/B, shares outstanding, EV, EV/EBITDA
    "incomeStatementHistory", # 4-year annual income statements
    "balanceSheetHistory",    # 4-year annual balance sheets
    "cashflowStatementHistory" # 4-year annual cash flow statements
])
url = f"https://query1.finance.yahoo.com/v10/finance/quoteSummary/{ticker}?modules={modules}"
data = json.loads(http_get(url))
result = data["quoteSummary"]["result"][0]
```

### Key fields to extract

| Field | Path in result |
|---|---|
| Current price | `financialData.currentPrice.raw` |
| Market cap | `summaryDetail.marketCap.raw` |
| Trailing P/E | `summaryDetail.trailingPE.raw` |
| Forward P/E | `summaryDetail.forwardPE.raw` |
| Dividend yield | `summaryDetail.dividendYield.raw` |
| Beta | `summaryDetail.beta.raw` |
| 52w high / low | `summaryDetail.fiftyTwoWeekHigh.raw` / `fiftyTwoWeekLow.raw` |
| Avg daily volume | `summaryDetail.averageVolume.raw` |
| Gross margin | `financialData.grossMargins.raw` |
| Operating margin | `financialData.operatingMargins.raw` |
| Net margin | `financialData.profitMargins.raw` |
| ROE | `financialData.returnOnEquity.raw` |
| Debt/Equity | `financialData.debtToEquity.raw` |
| Free cash flow | `financialData.freeCashflow.raw` |
| Operating CF | `financialData.operatingCashflow.raw` |
| EBITDA | `financialData.ebitda.raw` |
| EPS (trailing) | `defaultKeyStatistics.trailingEps.raw` |
| EPS (forward) | `defaultKeyStatistics.forwardEps.raw` |
| Book value/share | `defaultKeyStatistics.bookValue.raw` |
| P/B | `defaultKeyStatistics.priceToBook.raw` |
| Shares outstanding | `defaultKeyStatistics.sharesOutstanding.raw` |
| EV | `defaultKeyStatistics.enterpriseValue.raw` |
| EV/EBITDA | `defaultKeyStatistics.enterpriseToEbitda.raw` |

### 1b. Historical Price Data (for trend context)

```python
import time
period1 = int(time.time()) - 5 * 365 * 24 * 3600  # 5 years ago
period2 = int(time.time())
url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?period1={period1}&period2={period2}&interval=1mo"
price_data = json.loads(http_get(url))
# timestamps: price_data["chart"]["result"][0]["timestamp"]
# close prices: price_data["chart"]["result"][0]["indicators"]["quote"][0]["close"]
```

Use this to derive 5-year price trend and compare entry point relative to range.

---

## Step 2 — Fetch Analyst & Peer Data (KLSE Screener)

```python
code = "1155"  # ticker without .KL
url = f"https://www.klsescreener.com/v2/stocks/view/{code}"
html = http_get(url)
```

Parse from HTML:
- **Consensus target price** — look for table row labelled "Target Price" or analyst consensus section
- **Buy / Hold / Sell count** — analyst recommendation breakdown
- **Sector** — used in Step 5
- **Peer list** — same-sector stocks with P/E and P/B for relative comparison

Use `html.parser.HTMLParser` or simple string search to extract table data. Flag if KLSE Screener returns no analyst data (common for small caps).

---

## Step 3 — Fetch Analyst Calls & Dividend History (i3investor)

```python
code = "1155"
# Analyst calls
url = f"https://klse.i3investor.com/web/stock/overview.jsp?code={code}"
html = http_get(url)

# Dividend history
url = f"https://klse.i3investor.com/web/entitle/list.jsp?code={code}"
html = http_get(url)
```

Extract:
- Individual analyst house calls with dates and target prices
- Upgrade / downgrade trend (last 6 months)
- Dividend per share per year (last 5 years) — for DDM and yield history
- Ex-date and payment date for next upcoming dividend

---

## Step 4 — Fetch Bursa Announcements

```python
url = f"https://www.bursamalaysia.com/market_information/announcements/company_announcement?company={code}&type=all"
html = http_get(url)
```

Scan latest 20 announcements for:
- **Quarterly results (QR)** — note EPS trend, revenue trend vs prior year
- **Substantial shareholder notices (Form 29A)** — flag if EPF, PNB, KWAP hold >5% (positive signal) or if major shareholder reducing stake (negative signal)
- **Insider transactions (Form 29B)** — director buying = bullish signal; selling = flag
- **Rights issues / private placements** — dilution risk; adjust shares outstanding
- **Warrants outstanding** — check if any warrant conversion would dilute EPS materially

If no recent QR in the last 90 days, note as data gap.

---

## Step 5 — Detect Sector & Company Type

Use sector from KLSE Screener + company name heuristics to classify:

| Classification | Detection Rule | Valuation Approach |
|---|---|---|
| Bank | Sector = "Banking" or "Finance" | P/B heavy, add NIM / loan metrics |
| REIT | Name contains "REIT" or sector = "REITS" | DDM heavy, add DPU / gearing |
| Plantation | Sector = "Plantation" | DCF + EV/EBITDA, note CPO sensitivity |
| Construction | Sector = "Construction" | EV/EBITDA, note orderbook |
| Gloves / Manufacturing | Sector = "Industrial Products" + key products check | DCF + P/E, note ASP / USD sensitivity |
| Utility / Telco | Sector = "Utilities" or "Telecommunications" | DDM + DCF, stable cash flow |
| Property | Sector = "Property" | P/B + RNAV approach |
| General / Mixed | All others | Equal-weight across applicable models |

---

## Step 6 — Liquidity Flag

```python
avg_volume = result["summaryDetail"]["averageVolume"]["raw"]
current_price = result["financialData"]["currentPrice"]["raw"]
avg_daily_value_myr = avg_volume * current_price
```

- If `avg_daily_value_myr < 500_000`: flag as **ILLIQUID** in report header. Note that bid-ask spread and exit risk are elevated. Continue analysis but caveat all conclusions.
- If `avg_daily_value_myr < 100_000`: flag as **HIGHLY ILLIQUID**. Valuation models still apply but treat with extra scepticism.

---

## Step 7 — Financial Health Check

Compute from Yahoo Finance data (Steps 1a multi-year statements):

### Profitability
- Revenue 3-year CAGR: `(revenue_yr3 / revenue_yr0) ^ (1/3) - 1`
- Gross / operating / net margin trend: stable, expanding, or deteriorating?
- ROE: target > 10–15%. Below 8% = weak. Above 20% = strong.

### Balance Sheet
- Debt-to-equity: < 0.5 = conservative; 0.5–1.5 = moderate; > 1.5 = high leverage
- Current ratio: > 1.5 preferred; < 1.0 = short-term liquidity risk
- Net cash / net debt: `cash_and_equivalents - total_debt`

### Cash Flow Quality
- Compare operating CF to net profit each year. If net profit consistently exceeds operating CF, flag earnings quality concern.
- Free cash flow = `operating_CF - capex`
- FCF yield = `FCF / market_cap` — above 5% is attractive

### Sector-Specific Health Metrics

**Banks** — from Bursa QR announcements (Yahoo Finance does not carry these):
- Net interest margin (NIM): target > 2%
- Gross impaired loan (GIL) ratio: < 2% healthy
- CET1 ratio: > 13% well-capitalised
- Loan growth vs industry

**REITs** — from i3investor dividend history + Bursa QR:
- Distribution per unit (DPU) trend: stable or growing?
- Gearing ratio: regulatory cap is 50%; flag if > 40%
- NAV premium/discount: `current_price / book_value_per_share - 1`

**Plantation** — flag in report if CPO spot price not fetched:
- CPO price sensitivity: state current CPO price (search `CPO Malaysia spot price`) and note RM per tonne
- FFB yield and cost per tonne from annual report (flag as manual lookup if not available)

**Construction** — from Bursa announcements:
- Orderbook size and orderbook-to-revenue cover (years of revenue visibility)
- Flag if cover < 1 year

**Gloves / Manufacturing**:
- ASP trend (average selling price) from QR commentary
- USD/MYR sensitivity: note if revenue is USD-denominated

Assign overall health rating:
- **Strong**: ROE > 15%, positive FCF, net cash or low debt, margins stable/growing
- **Moderate**: ROE 8–15%, FCF positive but thin, manageable debt
- **Weak**: ROE < 8%, FCF negative, high leverage, or earnings quality concerns

---

## Step 8 — Valuation Models

### Model 1: DCF (Discounted Cash Flow)

Best for: growth companies, stable cash-generative businesses.

```python
# Inputs
fcf_base = result["financialData"]["freeCashflow"]["raw"]
shares = result["defaultKeyStatistics"]["sharesOutstanding"]["raw"]
net_debt = total_debt - cash  # from balance sheet
growth_rate_yr1_5 = 0.08      # use revenue CAGR as proxy, cap at 15%
growth_rate_terminal = 0.03   # conservative for Malaysia
wacc = 0.10                   # 8–12% typical; use 10% default; adjust for beta

# DCF calculation
fcf = fcf_base
pv_sum = 0
for yr in range(1, 6):
    fcf *= (1 + growth_rate_yr1_5)
    pv_sum += fcf / (1 + wacc) ** yr

terminal_value = fcf * (1 + growth_rate_terminal) / (wacc - growth_rate_terminal)
pv_terminal = terminal_value / (1 + wacc) ** 5
intrinsic_value = (pv_sum + pv_terminal - net_debt) / shares
```

State WACC assumptions explicitly. Run a sensitivity: ±1% WACC and ±2% growth gives a fair value range, not a single number.

### Model 2: P/E Relative Valuation

```python
eps_trailing = result["defaultKeyStatistics"]["trailingEps"]["raw"]
eps_forward  = result["defaultKeyStatistics"]["forwardEps"]["raw"]
current_pe   = result["summaryDetail"]["trailingPE"]["raw"]
# target_pe: use 5-year median P/E if available, else sector peer average from KLSE Screener
fair_value_pe = eps_forward * target_pe
```

- Compare current P/E vs company's own historical P/E range (from 5-year price / EPS data)
- Compare vs sector peer average P/E from KLSE Screener
- If company is loss-making, skip this model and flag

### Model 3: P/B Relative Valuation

Best for: banks, REITs, property.

```python
bvps = result["defaultKeyStatistics"]["bookValue"]["raw"]
current_pb = result["defaultKeyStatistics"]["priceToBook"]["raw"]
# target_pb: peer average or historical average; for banks 1.0–1.5x typical
fair_value_pb = bvps * target_pb
```

### Model 4: EV/EBITDA

Best for: capital-intensive, leveraged companies, M&A context.

```python
ebitda = result["financialData"]["ebitda"]["raw"]
net_debt = total_debt - cash
shares = result["defaultKeyStatistics"]["sharesOutstanding"]["raw"]
# target_ev_ebitda: sector peer average from KLSE Screener
target_ev = ebitda * target_ev_ebitda
fair_value_ev = (target_ev - net_debt) / shares
```

### Model 5: Dividend Discount Model (DDM)

Best for: REITs, utilities, banks, mature dividend stocks. Skip if dividend history is absent or inconsistent.

```python
dps_latest = # from i3investor dividend history, last 12 months total
dps_growth  = # 3-year DPS CAGR from i3investor history
required_return = 0.07  # risk-free rate (~4% MGS) + equity risk premium
fair_value_ddm = dps_latest * (1 + dps_growth) / (required_return - dps_growth)
```

### Weighting by Company Type

| Company Type | DCF | P/E | P/B | EV/EBITDA | DDM |
|---|---|---|---|---|---|
| Growth | 40% | 30% | 10% | 20% | 0% |
| Bank | 10% | 20% | 40% | 0% | 30% |
| REIT | 10% | 0% | 30% | 0% | 60% |
| Plantation | 30% | 20% | 10% | 40% | 0% |
| Construction | 20% | 20% | 10% | 50% | 0% |
| Utility / Telco | 30% | 20% | 10% | 10% | 30% |
| Property | 20% | 20% | 40% | 20% | 0% |
| General / Mixed | 25% | 25% | 20% | 20% | 10% |

Only include a model in the weighted average if it produced a valid result. Renormalise weights if a model is skipped.

---

## Step 9 — Benchmark Context (KLCI)

```python
# Fetch FBM KLCI index P/E and P/B for market context
url = "https://query1.finance.yahoo.com/v10/finance/quoteSummary/%5EKLSE?modules=summaryDetail,defaultKeyStatistics"
klci_data = json.loads(http_get(url))
klci_pe = klci_data["quoteSummary"]["result"][0]["summaryDetail"]["trailingPE"]["raw"]
klci_pb = klci_data["quoteSummary"]["result"][0]["defaultKeyStatistics"]["priceToBook"]["raw"]
```

- If stock P/E > KLCI P/E by more than 30% without superior growth justification, downgrade stance one notch
- If stock P/E < KLCI P/E by more than 20% with comparable or better ROE, this strengthens BUY case
- State relative premium/discount to market explicitly in the report

---

## Step 10 — Catalyst & Risk Assessment

**Upside catalysts** (check recent Bursa announcements and news):
- New contract wins or orderbook replenishment
- Earnings beat vs analyst estimates
- Dividend increase or special dividend announcement
- Sector tailwind (policy support, commodity price rise)
- M&A: acquisition that is EPS-accretive

**Downside risks**:
- Customer / revenue concentration (single client > 30% of revenue)
- Rising input costs with limited pricing power
- Currency risk: RM depreciation for import-heavy; RM appreciation for export-heavy
- Regulatory or policy change (especially for banks, telcos, utilities)
- Upcoming rights issue or large placement dilution
- Management change or governance concern (from Bursa announcements)

**Timeline**: State how long the investment thesis takes to play out. Short (< 6 months), medium (6–18 months), long (> 18 months).

---

## Step 11 — Output Report

```
============================================================
MALAYSIA STOCK ANALYSIS REPORT
============================================================
Company     : [Full Name] ([Ticker].KL)
Date        : [YYYY-MM-DD]
Current Price: RM X.XX
Sector      : [Sector] — [Main Market / ACE Market]
Company Type: [Growth / Bank / REIT / Plantation / etc.]
[ILLIQUID FLAG if avg daily value < RM500k]

--- FINANCIAL HEALTH ---
Revenue 3Y CAGR    : X%
Net Margin         : X% ([trend: stable/expanding/deteriorating])
ROE                : X%
Debt-to-Equity     : X.X
Net Cash / (Debt)  : RM Xm
FCF Yield          : X%
Health Assessment  : Strong / Moderate / Weak
[Sector-specific metrics if applicable]

--- LIQUIDITY ---
Avg Daily Value    : RM Xm
Liquidity Status   : Normal / Illiquid / Highly Illiquid

--- VALUATION MODELS ---
Model               Fair Value (RM)   Weight   Notes
DCF                 X.XX              XX%      WACC X%, growth X%
P/E Relative        X.XX              XX%      Target P/E: Xx (peer avg: Xx)
P/B Relative        X.XX              XX%      Target P/B: Xx (peer avg: Xx)
EV/EBITDA           X.XX              XX%      Target EV/EBITDA: Xx
DDM                 X.XX              XX%      DPS growth X%, req. return X%
─────────────────────────────────────────────
Weighted Fair Value : RM X.XX

--- ANALYST CONSENSUS ---
Consensus Target    : RM X.XX  (X Buy / X Hold / X Sell)
vs Own Fair Value   : [above / below by X%] — [explanation of gap if > 15%]

--- BENCHMARK CONTEXT ---
Stock P/E           : Xx  vs  KLCI P/E: Xx  →  [X% premium/discount]
Stock P/B           : Xx  vs  KLCI P/B: Xx

--- FAIR VALUE SUMMARY ---
Weighted Fair Value : RM X.XX
Margin of Safety    : RM X.XX  (20% below fair value)
Upside / Downside   : X%

--- TRADE PARAMETERS ---
Entry Range         : RM X.XX – X.XX  (fair value – 15% to – 20%)
Stop-Loss Level     : RM X.XX  (below 52-week low OR thesis invalidation price)
Thesis Invalidation : [specific event that would invalidate the investment case]
Review Trigger      : [e.g. "next QR release", "CPO price drops below RM3,800/tonne"]
Investment Timeline : Short / Medium / Long term

--- RECOMMENDATION ---
Stance              : BUY / HOLD / SELL / AVOID

Key Catalysts:
  1. [catalyst]
  2. [catalyst]

Key Risks:
  1. [risk]
  2. [risk]

--- DATA GAPS ---
[List any data that could not be fetched, was missing, or requires manual lookup]
============================================================
```

---

## Margin of Safety Rule

Flag as **BUY** only if current price is at least **15–20% below** weighted fair value. This accounts for model estimation error, data lag, and Malaysia-specific liquidity risk.

If price is within 5% of fair value: **HOLD**.
If price is more than 10% above fair value: **SELL** / **AVOID**.

---

## Data Gap Handling

- If Yahoo Finance returns no data for a field: note as "N/A — not available from Yahoo Finance" and exclude from affected model
- If KLSE Screener returns no analyst coverage: note as "No analyst coverage — small cap" and skip consensus cross-check
- If DDM inputs unavailable (no dividend history): skip DDM, renormalise weights
- If Bursa announcements page is inaccessible: note and proceed without insider/shareholder data
- Never silently substitute zeros or averages for missing data — always flag explicitly

---

## Notes
- All monetary values in Ringgit Malaysia (RM) unless stated otherwise
- Warrant dilution: if warrants outstanding > 5% of shares, compute diluted share count and note impact on per-share values
- For ACE Market stocks: apply a 20–30% liquidity/risk discount to fair value vs equivalent Main Market stock
- WACC default 10%; adjust upward for high-beta (> 1.3) or highly leveraged companies; adjust downward for blue chips with beta < 0.7
