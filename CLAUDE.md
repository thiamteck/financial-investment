# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Purpose

This repo is a version-controlled store for Claude Code skills — both self-created and 3rd-party installed locally — focused on financial investment analysis.

`.claude/skills/` is intentionally version-controlled here. Any new skill installed or authored locally should be committed to this repo.

## Skill Structure

Each skill lives in its own subdirectory under `.claude/skills/<skill-name>/`:

```
.claude/skills/
  klse-valuation/
    SKILL.md          # skill definition and instructions
    scripts/
      fetch.py        # Yahoo Finance HTTP auth (cookie + crumb), yf_get(), http_get()
      analyse.py      # full analysis pipeline: Steps 0–11, valuation models, report
```

The `.claude/skills/<skill-name>.skill` file at the root of `.claude/skills/` is the skill manifest read by Claude Code.

## Running the KLSE Valuation Skill

From within the skill directory:

```
python scripts/analyse.py <TICKER.KL>
```

Examples:
```
python scripts/analyse.py 1155.KL   # Maybank
python scripts/analyse.py 5212.KL   # Pavilion REIT
```

The script uses Python stdlib only (`urllib`, `json`, `ssl`, `http.cookiejar`, `re`) — no pip installs needed.

**Ticker resolution:** if only a company name is known, run a WebSearch for the Bursa stock code before invoking the script. The skill's SKILL.md documents this as Step 0.

**Yahoo Finance auth:** Yahoo Finance requires a session cookie + crumb token. `fetch.py` handles this via `init_session()` — always use `yf_get()` instead of calling Yahoo Finance URLs directly.

## Key Conventions

- All monetary values in RM unless stated otherwise.
- Scripts must remain stdlib-only — no third-party libraries.
- If a data source fetch fails, note the gap and continue — never abort the analysis.
- ACE Market stocks require a 20–30% additional discount to fair value vs equivalent Main Market stock.
- WACC default: 10%; adjust ±1% for beta outliers.
