# Skill: Malaysia Listed Company Fair Value Analysis

## Purpose
Analyse a given Bursa Malaysia listed company and evaluate its fair value using multiple valuation models. Output a structured report with a recommended fair price and investment stance.

---

## Data Sources

### 1. Yahoo Finance (`yfinance` Python library)
- **Ticker format**: `XXXX.KL` (e.g. `1155.KL` for Maybank)
- **Use for**:
  - Historical price data (OHLCV)
  - Income statement, balance sheet, cash flow (3–5 years)
  - Key ratios: P/E, P/B, EV/EBITDA, dividend yield, market cap
  - Shares outstanding, beta
- **Strength**: Structured API, no scraping, bulk-friendly

### 2. KLSE Screener (`klsescreener.com`)
- **Use for**:
  - Analyst consensus target price
  - Individual analyst recommendations (Buy/Hold/Sell)
  - Peer comparison within same sector
  - Sector classification (Main Market / ACE Market)
- **Strength**: Malaysia-specific, clean HTML tables, consistent URL structure

### 3. i3investor (`klse.i3investor.com`)
- **Use for**:
  - Individual analyst house calls with dates
  - Upgrade/downgrade trend tracking
  - Dividend history
  - Forum sentiment (optional qualitative signal)
- **Strength**: Aggregates multiple analyst houses, tracks call history over time

---

## Analysis Framework

### Stage 1 — Business Understanding (Qualitative)
- What does the company do and how does it earn revenue?
- Industry and sector outlook
- Competitive moat and key risks
- Management track record
- *Sources: Annual report, Bursa announcements, news*

### Stage 2 — Financial Health Check
Pull last 3–5 years data from Yahoo Finance and assess:

**Profitability**
- Revenue growth trend (consistent or volatile?)
- Gross margin, operating margin, net margin (stable or expanding?)
- ROE target: above 10–15%

**Balance Sheet**
- Debt-to-equity ratio (is leverage manageable?)
- Current ratio (short-term liquidity)
- Net cash or net debt position

**Cash Flow Quality**
- Operating cash flow vs net profit (do they track together?)
- Free cash flow = Operating CF - Capex
- Red flag: net profit growing but FCF declining

### Stage 3 — Valuation Models

#### Model 1: DCF (Discounted Cash Flow)
- Project free cash flow for 5–10 years
- Apply terminal growth rate (2–4% for mature companies)
- Discount rate (WACC): typically 8–12% for Malaysian stocks
- Terminal value = FCF_final × (1 + g) / (WACC - g)
- Intrinsic value = Sum of PV of FCFs + PV of terminal value / shares outstanding

#### Model 2: P/E Relative Valuation
- Get current P/E from Yahoo Finance
- Compare vs company's own 5-year historical average P/E
- Compare vs sector peer average P/E (from KLSE Screener)
- Fair value = Normalised EPS × Target P/E multiple

#### Model 3: P/B Relative Valuation
- Best for asset-heavy companies (banks, REITs, property)
- Compare current P/B vs historical average and peers
- Fair value = Book value per share × Target P/B multiple

#### Model 4: EV/EBITDA Relative Valuation
- Best for capital-intensive or leveraged companies
- Compare vs sector peers
- Fair value derived from target EV/EBITDA × EBITDA / shares outstanding (net of debt)

#### Model 5: Dividend Discount Model (DDM)
- Best for stable dividend-paying stocks (REITs, utilities, banks)
- Fair value = Expected DPS / (Required return - Dividend growth rate)
- Use when dividend yield is primary investor attraction

### Stage 4 — Analyst Sentiment Cross-Check
- Retrieve consensus target price from KLSE Screener
- Review individual analyst calls from i3investor
- Note any recent upgrade or downgrade trend
- If own DCF differs significantly from consensus, identify and explain the gap
- **Rule**: Form own view first, use consensus as sanity check only

### Stage 5 — Catalyst & Risk Assessment
- **Upside catalysts**: new contracts, earnings beat, sector tailwind, M&A
- **Downside risks**: regulatory change, customer concentration, rising input costs, currency
- **Timeline**: How long for thesis to play out?

---

## Fair Value Calculation

Triangulate across models and apply weights based on company type:

| Company Type | Recommended Weight |
|---|---|
| Growth company | DCF heavy (40–50%) |
| Asset-heavy (bank, property) | P/B heavy (40–50%) |
| Stable dividend stock | DDM heavy (40–50%) |
| General / mixed | Equal weight across applicable models |

### Example Output Table

| Valuation Method | Fair Value (RM) | Weight |
|---|---|---|
| DCF | 3.80 | 30% |
| P/E Relative | 3.40 | 25% |
| P/B Relative | 3.60 | 20% |
| EV/EBITDA | 3.50 | 15% |
| Analyst Consensus | 3.20 | 10% |
| **Weighted Fair Value** | **3.57** | 100% |

---

## Output Report Structure

```
Company: [Name] ([Ticker].KL)
Date: [Date]
Current Price: RM X.XX
Sector: [Sector]

--- FINANCIAL HEALTH SUMMARY ---
Revenue Growth (3Y CAGR): X%
Net Margin: X%
ROE: X%
Debt-to-Equity: X
Free Cash Flow: RM Xm
Health Assessment: Strong / Moderate / Weak

--- VALUATION SUMMARY ---
DCF Fair Value: RM X.XX
P/E Fair Value: RM X.XX
P/B Fair Value: RM X.XX
DDM Fair Value: RM X.XX (if applicable)
Analyst Consensus Target: RM X.XX

Weighted Fair Value: RM X.XX
Upside / Downside: X%

--- RECOMMENDATION ---
Fair Value: RM X.XX
Margin of Safety (15–20% below fair value): RM X.XX
Stance: BUY / HOLD / SELL

Key Catalysts: [list]
Key Risks: [list]
```

---

## Margin of Safety Rule
Only flag as BUY if current price is at least **15–20% below** weighted fair value, to account for model error and uncertainty.

---

## Notes for Skill Implementation
- Accept input as stock ticker (e.g. `1155.KL`) or company name
- If company name given, resolve to ticker first via KLSE Screener search
- Handle missing data gracefully (e.g. no dividend history = skip DDM)
- Flag data gaps explicitly in output rather than silently skipping
- All monetary values in Ringgit Malaysia (RM) unless otherwise stated
