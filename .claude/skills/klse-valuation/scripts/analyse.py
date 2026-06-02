"""
klse-valuation: main analysis script.
Usage: python analyse.py <ticker_or_name>
  e.g. python analyse.py 1155.KL
       python analyse.py maybank
       python analyse.py "Pavilion REIT"
"""

import sys
import urllib.parse
import json
import time
import math
from fetch import init_session, yf_get, http_get


# ---------------------------------------------------------------------------
# Step 0 — Resolve ticker
# ---------------------------------------------------------------------------

def resolve_ticker(input_str):
    if input_str.upper().endswith(".KL"):
        return input_str.upper()

    import re

    # Try Yahoo Finance search API — append "KL" to bias toward Bursa results
    try:
        query = urllib.parse.quote(f"{input_str} KL")
        url = f"https://query1.finance.yahoo.com/v1/finance/search?q={query}&quotesCount=10&newsCount=0&enableFuzzyQuery=false"
        data = json.loads(http_get(url))
        for q in data.get("quotes", []):
            sym = q.get("symbol", "")
            if sym.endswith(".KL") and q.get("quoteType") == "EQUITY":
                print(f"[INFO] Resolved via Yahoo Finance search: {sym}", file=sys.stderr)
                return sym
    except Exception as e:
        print(f"[WARN] Yahoo Finance search failed: {e}", file=sys.stderr)

    # If running standalone (not via Claude skill), we cannot call WebSearch.
    # Instruct the user to resolve manually.
    sys.exit(
        f"ERROR: Could not auto-resolve '{input_str}' to a .KL ticker.\n"
        f"  Tip: Search for '{input_str} Bursa stock code' and pass the ticker directly.\n"
        f"  Example: python analyse.py 5212.KL"
    )


# ---------------------------------------------------------------------------
# Step 1 — Yahoo Finance data
# ---------------------------------------------------------------------------

def fetch_yf(ticker):
    modules = ",".join([
        "summaryDetail",
        "financialData",
        "defaultKeyStatistics",
        "incomeStatementHistory",
        "balanceSheetHistory",
        "cashflowStatementHistory",
    ])
    url = f"https://query1.finance.yahoo.com/v10/finance/quoteSummary/{ticker}?modules={modules}"
    data = yf_get(url)
    return data["quoteSummary"]["result"][0]


def fetch_price_history(ticker):
    period1 = int(time.time()) - 5 * 365 * 24 * 3600
    period2 = int(time.time())
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?period1={period1}&period2={period2}&interval=1mo"
    return yf_get(url)


def fetch_klci():
    """
    Yahoo Finance does not expose trailing P/E or P/B for ^KLSE (index, not stock).
    forwardPE from summaryDetail is the closest available proxy.
    P/B is not available — we skip it for the benchmark.
    """
    url = "https://query1.finance.yahoo.com/v10/finance/quoteSummary/%5EKLSE?modules=summaryDetail,defaultKeyStatistics"
    data = yf_get(url)
    return data["quoteSummary"]["result"][0]


# ---------------------------------------------------------------------------
# Step 2 — KLSE Screener
# ---------------------------------------------------------------------------

def fetch_klse_screener(code):
    try:
        html = http_get(f"https://www.klsescreener.com/v2/stocks/view/{code}")
        return html
    except Exception as e:
        return None


# ---------------------------------------------------------------------------
# Step 3 — i3investor
# ---------------------------------------------------------------------------

def fetch_i3investor(code):
    results = {}
    for key, path in [("overview", "stock/overview.jsp"), ("dividends", "entitle/list.jsp")]:
        try:
            results[key] = http_get(f"https://klse.i3investor.com/web/{path}?code={code}")
        except Exception as e:
            results[key] = None
    return results


# ---------------------------------------------------------------------------
# Step 4 — Bursa announcements
# ---------------------------------------------------------------------------

def fetch_bursa(code):
    try:
        return http_get(
            f"https://www.bursamalaysia.com/market_information/announcements/"
            f"company_announcement?company={code}&type=all"
        )
    except Exception as e:
        return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def g(d, *keys):
    """Safe nested dict getter — returns None if any key is missing."""
    for k in keys:
        if not isinstance(d, dict):
            return None
        d = d.get(k)
    return d if d not in (None, {}) else None


def detect_sector(ticker, klse_html):
    """Return (sector_label, company_type) from KLSE Screener HTML or name heuristic.

    KLSE Screener emits: <span class="text-muted">Main Market : Banking</span>
    """
    import re
    name = ticker.upper()
    if "REIT" in name:
        return "Real Estate Investment Trusts — Main Market", "REIT"
    if klse_html:
        # Matches "Main Market : Banking" or "ACE Market : Technology" etc.
        m = re.search(r'(Main Market|ACE Market)\s*:\s*([^<]+)', klse_html)
        if m:
            market_type = m.group(1).strip()
            sector      = m.group(2).strip()
            label       = f"{sector} — {market_type}"
            s = sector.lower()
            if "bank" in s or "financ" in s:
                return label, "Bank"
            if "reit" in s or "real estate" in s:
                return label, "REIT"
            if "plantation" in s:
                return label, "Plantation"
            if "construction" in s:
                return label, "Construction"
            if "utility" in s or "telecommun" in s:
                return label, "Utility/Telco"
            if "property" in s:
                return label, "Property"
            if "industrial" in s or "technolog" in s:
                return label, "Manufacturing"
            return label, "General"
    return "Unknown", "General"


WEIGHTS = {
    "Bank":          {"DCF": 0.10, "PE": 0.20, "PB": 0.40, "EVEBITDA": 0.00, "DDM": 0.30},
    "REIT":          {"DCF": 0.10, "PE": 0.00, "PB": 0.30, "EVEBITDA": 0.00, "DDM": 0.60},
    "Plantation":    {"DCF": 0.30, "PE": 0.20, "PB": 0.10, "EVEBITDA": 0.40, "DDM": 0.00},
    "Construction":  {"DCF": 0.20, "PE": 0.20, "PB": 0.10, "EVEBITDA": 0.50, "DDM": 0.00},
    "Utility/Telco": {"DCF": 0.30, "PE": 0.20, "PB": 0.10, "EVEBITDA": 0.10, "DDM": 0.30},
    "Property":      {"DCF": 0.20, "PE": 0.20, "PB": 0.40, "EVEBITDA": 0.20, "DDM": 0.00},
    "Manufacturing": {"DCF": 0.35, "PE": 0.30, "PB": 0.10, "EVEBITDA": 0.25, "DDM": 0.00},
    "General":       {"DCF": 0.25, "PE": 0.25, "PB": 0.20, "EVEBITDA": 0.20, "DDM": 0.10},
}


# ---------------------------------------------------------------------------
# Step 8 — Valuation models
# ---------------------------------------------------------------------------

def run_dcf(op_cf, fcf, net_income, div_payout, net_debt, shares, rev_cagr, company_type, beta):
    """
    For banks: use retained earnings (net_income * (1 - payout)) as FCF proxy.
    For all others: prefer FCF, fall back to op_cf.
    WACC default 10%; lower for blue chips (beta < 0.7), higher for leveraged/high-beta.
    """
    if company_type == "Bank":
        if net_income and div_payout is not None:
            fcf_base = net_income * (1 - div_payout)
            note = "retained earnings proxy (bank)"
        else:
            return None, None, None, "skipped — bank net income unavailable"
    elif company_type == "REIT":
        # REITs distribute most income; use op_cf as distributable income proxy.
        # Negative FCF is normal (property capex) and should not drive DCF.
        fcf_base = op_cf
        note = "op CF proxy (REIT — FCF excluded)"
        if fcf_base and fcf_base < 0:
            return None, None, None, "skipped — negative op CF, use DDM instead"
    else:
        fcf_base = fcf or op_cf
        note = "FCF" if fcf else "op CF proxy"

    if not fcf_base or not shares:
        return None, None, None, "skipped — cash flow data unavailable"

    wacc = 0.10
    if beta and beta < 0.7:
        wacc = 0.09
    elif beta and beta > 1.3:
        wacc = 0.11

    g5   = min(rev_cagr or 0.04, 0.15)
    gterm = 0.03

    pv_sum = 0
    f = fcf_base
    for yr in range(1, 6):
        f *= (1 + g5)
        pv_sum += f / (1 + wacc) ** yr
    tv    = f * (1 + gterm) / (wacc - gterm)
    pv_tv = tv / (1 + wacc) ** 5
    base  = (pv_sum + pv_tv - (net_debt or 0)) / shares

    lo = base * (1 - 0.12)  # WACC +1%
    hi = base * (1 + 0.14)  # WACC -1%
    desc = f"WACC {wacc*100:.0f}%, growth {g5*100:.0f}%, {note} (range RM {lo:.2f}–{hi:.2f})"
    return base, lo, hi, desc


def run_pe(eps_fwd, target_pe):
    if not eps_fwd or eps_fwd <= 0:
        return None, "skipped — negative or missing EPS"
    val = eps_fwd * target_pe
    return val, f"target P/E {target_pe:.1f}x"


def run_pb(bvps, target_pb):
    if not bvps:
        return None, "skipped — book value unavailable"
    return bvps * target_pb, f"target P/B {target_pb:.2f}x"


def run_ev_ebitda(ebitda, net_debt, shares, target_multiple):
    if not ebitda or not shares:
        return None, "skipped — EBITDA unavailable"
    val = (ebitda * target_multiple - (net_debt or 0)) / shares
    return val, f"target EV/EBITDA {target_multiple:.1f}x"


def run_ddm(dps, dps_growth, req_ret=0.07):
    if not dps or dps <= 0:
        return None, "skipped — no dividend history"
    if req_ret <= dps_growth:
        return None, "skipped — growth rate >= required return"
    val = dps * (1 + dps_growth) / (req_ret - dps_growth)
    return val, f"DPS RM {dps:.3f}, growth {dps_growth*100:.1f}%, req ret {req_ret*100:.0f}%"


def weighted_average(model_results, weights):
    """model_results: dict of name -> (value, desc). weights: dict of name -> float."""
    total_w = 0
    total_v = 0
    for name, (val, _) in model_results.items():
        w = weights.get(name, 0)
        if val and w:
            total_v += val * w
            total_w += w
    if not total_w:
        return None
    return total_v / total_w


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    raw_input = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else None
    if not raw_input:
        sys.exit("Usage: python analyse.py <ticker_or_company_name>")

    print(f"Initialising session...", file=sys.stderr)
    init_session()

    # Step 0
    ticker = resolve_ticker(raw_input)
    code   = ticker.replace(".KL", "")
    print(f"Ticker: {ticker}", file=sys.stderr)

    # Step 1
    print("Fetching Yahoo Finance data...", file=sys.stderr)
    try:
        res = fetch_yf(ticker)
    except Exception as e:
        sys.exit(f"ERROR: Yahoo Finance fetch failed: {e}")

    sd  = res.get("summaryDetail", {})
    fd  = res.get("financialData", {})
    ks  = res.get("defaultKeyStatistics", {})
    inc = res.get("incomeStatementHistory", {}).get("incomeStatementHistory", [])
    bs  = res.get("balanceSheetHistory", {}).get("balanceSheetStatements", [])
    cf  = res.get("cashflowStatementHistory", {}).get("cashflowStatements", [])

    price     = g(fd,"currentPrice","raw") or g(sd,"regularMarketPrice","raw")
    mktcap    = g(sd,"marketCap","raw")
    pe_trail  = g(sd,"trailingPE","raw")
    pe_fwd    = g(sd,"forwardPE","raw")
    div_yield = g(sd,"dividendYield","raw")
    beta      = g(sd,"beta","raw")
    hi52      = g(sd,"fiftyTwoWeekHigh","raw")
    lo52      = g(sd,"fiftyTwoWeekLow","raw")
    avg_vol   = g(sd,"averageVolume","raw")
    nm        = g(fd,"profitMargins","raw")
    roe       = g(fd,"returnOnEquity","raw")
    de        = g(fd,"debtToEquity","raw")
    fcf       = g(fd,"freeCashflow","raw")
    op_cf     = g(fd,"operatingCashflow","raw")
    ebitda    = g(fd,"ebitda","raw")
    eps_trail = g(ks,"trailingEps","raw")
    eps_fwd   = g(ks,"forwardEps","raw")
    bvps      = g(ks,"bookValue","raw")
    pb        = g(ks,"priceToBook","raw")
    shares    = g(ks,"sharesOutstanding","raw")
    ev        = g(ks,"enterpriseValue","raw")
    ev_ebitda = g(ks,"enterpriseToEbitda","raw")

    # Multi-year revenue
    revs = [g(y,"totalRevenue","raw") for y in inc]
    revs = [r for r in revs if r]
    rev_cagr = None
    if len(revs) >= 2 and revs[-1] > 0:
        rev_cagr = (revs[0] / revs[-1]) ** (1 / (len(revs) - 1)) - 1

    # Net income (latest)
    net_income = g(inc[0], "netIncome", "raw") if inc else None

    # Dividend payout ratio estimate
    div_payout = None
    if div_yield and price and eps_trail and eps_trail > 0:
        dps_est    = div_yield * price
        div_payout = dps_est / eps_trail

    # Balance sheet (latest year)
    cash_latest = g(bs[0],"cash","raw") if bs else None
    debt_latest = g(bs[0],"totalDebt","raw") if bs else None
    cur_assets  = g(bs[0],"totalCurrentAssets","raw") if bs else None
    cur_liab    = g(bs[0],"totalCurrentLiabilities","raw") if bs else None
    net_debt    = (debt_latest or 0) - (cash_latest or 0)
    cur_ratio   = (cur_assets / cur_liab) if cur_assets and cur_liab else None

    # Liquidity
    adv = (avg_vol or 0) * (price or 0)
    if adv < 100_000:
        liquidity = "HIGHLY ILLIQUID"
    elif adv < 500_000:
        liquidity = "ILLIQUID"
    else:
        liquidity = "Normal"

    fcf_yield = (fcf / mktcap * 100) if fcf and mktcap else None

    # Health rating
    if roe and roe > 0.15 and fcf and fcf > 0 and net_debt <= 0:
        health = "Strong"
    elif roe and roe < 0.08:
        health = "Weak"
    else:
        health = "Moderate"

    # Step 2
    print("Fetching KLSE Screener...", file=sys.stderr)
    klse_html = fetch_klse_screener(code)

    # Step 3
    print("Fetching i3investor...", file=sys.stderr)
    i3 = fetch_i3investor(code)

    # Step 4
    print("Fetching Bursa announcements...", file=sys.stderr)
    bursa_html = fetch_bursa(code)

    # Step 5
    sector_label, company_type = detect_sector(ticker, klse_html)

    # Step 6 already done (adv/liquidity above)

    # Step 9 — KLCI benchmark
    print("Fetching KLCI benchmark...", file=sys.stderr)
    try:
        kd = fetch_klci()
        # ^KLSE index: trailingPE is not exposed — use forwardPE as proxy
        klci_pe = (g(kd, "summaryDetail", "trailingPE", "raw")
                   or g(kd, "summaryDetail", "forwardPE", "raw"))
        klci_pe_label = "forward P/E" if not g(kd, "summaryDetail", "trailingPE", "raw") else "trailing P/E"
        # P/B not available for index on Yahoo Finance
        klci_pb = None
    except Exception as e:
        klci_pe = klci_pb = None
        klci_pe_label = "P/E"

    # Step 8 — Valuation models
    weights = WEIGHTS.get(company_type, WEIGHTS["General"])

    # DPS estimate from yield (i3investor dividend page would improve this)
    dps_est    = (div_yield * price) if div_yield and price else None
    dps_growth = 0.02  # conservative default; replace with i3investor CAGR if parseable

    # Peer multiples defaults (replace with KLSE Screener parsed values when available)
    PEER_PE = {"Bank":10.0,"REIT":0.0,"Plantation":14.0,"Construction":12.0,
               "Utility/Telco":16.0,"Property":10.0,"Manufacturing":15.0,"General":14.0}
    PEER_PB = {"Bank":1.2,"REIT":1.0,"Plantation":1.5,"Construction":1.0,
               "Utility/Telco":1.8,"Property":0.8,"Manufacturing":1.5,"General":1.3}
    PEER_EV = {"Plantation":9.0,"Construction":8.0,"Utility/Telco":10.0,
               "Manufacturing":10.0,"General":9.0}

    target_pe_v = pe_fwd / 1.05 if pe_fwd else PEER_PE.get(company_type, 13.0)  # slight discount to fwd
    target_pe_v = PEER_PE.get(company_type, 13.0)  # use peer avg as anchor
    target_pb_v = PEER_PB.get(company_type, 1.2)
    target_ev_v = PEER_EV.get(company_type, 9.0)

    dcf_base, dcf_lo, dcf_hi, dcf_note = run_dcf(
        op_cf, fcf, net_income, div_payout, net_debt, shares, rev_cagr, company_type, beta
    )
    pe_base,  pe_note  = run_pe(eps_fwd, target_pe_v)
    pb_base,  pb_note  = run_pb(bvps, target_pb_v)
    ev_base,  ev_note  = run_ev_ebitda(ebitda, net_debt, shares, target_ev_v)
    ddm_base, ddm_note = run_ddm(dps_est, dps_growth)

    models = {
        "DCF":      (dcf_base, dcf_note),
        "PE":       (pe_base,  pe_note),
        "PB":       (pb_base,  pb_note),
        "EVEBITDA": (ev_base,  ev_note),
        "DDM":      (ddm_base, ddm_note),
    }

    weighted_fv = weighted_average(models, weights)
    mos         = weighted_fv * 0.80 if weighted_fv else None
    entry_lo    = weighted_fv * 0.80 if weighted_fv else None
    entry_hi    = weighted_fv * 0.85 if weighted_fv else None
    upside      = ((weighted_fv / price) - 1) * 100 if weighted_fv and price else None

    if price and weighted_fv:
        if price <= weighted_fv * 0.82:
            stance = "BUY"
        elif price >= weighted_fv * 1.10:
            stance = "SELL"
        else:
            stance = "HOLD"
    else:
        stance = "INSUFFICIENT DATA"

    pe_premium = ((pe_trail / klci_pe) - 1) * 100 if pe_trail and klci_pe else None
    pb_premium = None  # KLCI P/B not available from Yahoo Finance

    net_cash_str = "N/A"
    if cash_latest is not None or debt_latest is not None:
        nd = net_debt
        net_cash_str = f"RM {abs(nd)/1e9:.2f}B {'(net cash)' if nd < 0 else '(net debt)'}"

    # --- Build report ---
    MODEL_LABELS = {"DCF": "DCF", "PE": "P/E Relative", "PB": "P/B Relative",
                    "EVEBITDA": "EV/EBITDA", "DDM": "DDM"}

    lines = [
        "============================================================",
        "KLSE VALUATION REPORT",
        "============================================================",
        f"Company      : {ticker}",
        f"Date         : {time.strftime('%Y-%m-%d')}",
        f"Current Price: RM {price:.2f}" if price else "Current Price: N/A",
        f"Sector       : {sector_label}",
        f"Company Type : {company_type}",
    ]
    if liquidity != "Normal":
        lines.append(f"*** {liquidity} — avg daily value RM {adv/1e6:.2f}M ***")

    lines += [
        "",
        "--- FINANCIAL HEALTH ---",
        f"Revenue 3Y CAGR    : {rev_cagr*100:.1f}%" if rev_cagr is not None else "Revenue 3Y CAGR    : N/A",
        f"Net Margin         : {nm*100:.1f}%" if nm else "Net Margin         : N/A",
        f"ROE                : {roe*100:.1f}%" if roe else "ROE                : N/A",
        f"Debt-to-Equity     : {de:.1f}" if de else "Debt-to-Equity     : N/A",
        f"Net Cash / (Debt)  : {net_cash_str}",
        f"FCF Yield          : {fcf_yield:.1f}%" if fcf_yield else "FCF Yield          : N/A",
        f"Current Ratio      : {cur_ratio:.2f}" if cur_ratio else "Current Ratio      : N/A",
        f"Health Assessment  : {health}",
        "",
        "--- LIQUIDITY ---",
        f"Avg Daily Value    : RM {adv/1e6:.1f}M",
        f"Liquidity Status   : {liquidity}",
        "",
        "--- VALUATION MODELS ---",
        f"{'Model':<22} {'Fair Value':>12}   {'Weight':>6}   Notes",
    ]

    for key, label in MODEL_LABELS.items():
        val, note = models[key]
        w = weights.get(key, 0)
        if w == 0:
            continue
        if val is not None:
            lines.append(f"  {label:<20} RM {val:>7.2f}       {w*100:>3.0f}%   {note}")
        else:
            lines.append(f"  {label:<20}    {'SKIPPED':>7}       {w*100:>3.0f}%   {note}")

    if weighted_fv:
        lines += [
            "─" * 53,
            f"  {'Weighted Fair Value':<20} RM {weighted_fv:>7.2f}       100%",
        ]

    lines += [
        "",
        "--- ANALYST CONSENSUS ---",
        "Consensus Target    : DATA GAP — check KLSE Screener manually",
        "vs Own Fair Value   : N/A",
        "",
        "--- BENCHMARK CONTEXT ---",
        (f"Stock P/E  : {pe_trail:.1f}  vs  KLCI {klci_pe_label}: {klci_pe:.1f}  =>  {pe_premium:+.1f}% vs market"
         if pe_premium is not None else "Stock P/E  : N/A (KLCI P/E not available from Yahoo Finance)"),
        "Stock P/B  : N/A (KLCI index P/B not exposed by Yahoo Finance)",
        "",
        "--- FAIR VALUE SUMMARY ---",
        f"Weighted Fair Value : RM {weighted_fv:.2f}" if weighted_fv else "Weighted Fair Value : N/A",
        f"Margin of Safety    : RM {mos:.2f}  (20% below fair value)" if mos else "Margin of Safety    : N/A",
        f"Upside / Downside   : {upside:+.1f}%" if upside is not None else "Upside / Downside   : N/A",
        "",
        "--- TRADE PARAMETERS ---",
        (f"Entry Range         : RM {entry_lo:.2f} - {entry_hi:.2f}  (fair value -15% to -20%)"
         if entry_lo else "Entry Range         : N/A"),
        f"Stop-Loss Level     : RM {lo52:.2f}  (52-week low)" if lo52 else "Stop-Loss Level     : N/A",
        "Thesis Invalidation : [define based on sector — see SKILL.md Step 10]",
        "Review Trigger      : Next quarterly results (QR)",
        "Investment Timeline : [Short / Medium / Long — assess from catalyst timeline]",
        "",
        "--- RECOMMENDATION ---",
        f"Stance              : {stance}",
        "",
        "Key Catalysts       : [complete from Bursa announcements and news — Step 10]",
        "Key Risks           : [complete from Bursa announcements and news — Step 10]",
        "",
        "--- DATA GAPS ---",
        "  - Analyst consensus: fetch manually from KLSE Screener",
        "  - i3investor dividend history: used default DPS growth 2% — verify for DDM",
        "  - Bursa QR bank metrics (NIM, GIL, CET1): manual lookup required for banks",
        "  - Catalysts and risks: complete from Step 10 after reviewing announcements",
        "============================================================",
    ]

    report = "\n".join(lines)
    print(report)


if __name__ == "__main__":
    main()
