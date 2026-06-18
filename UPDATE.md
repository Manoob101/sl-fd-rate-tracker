# Daily update — how it works

Updating is now a **pure Selenium Python scraper** (no Claude / no API key). It
runs unattended via `launchd` every morning.

## The pipeline

```
launchd (07:00) → scripts/daily.sh
                    ├─ .venv/bin/python scripts/scrape.py   # headless Chromium scrape
                    │     → updates docs/data/rates.json
                    │     → runs scripts/build.py (shim + history)
                    └─ git add docs/data && commit && push  # GitHub Pages redeploys
```

## Run it manually

```bash
.venv/bin/python scripts/scrape.py            # all banks
.venv/bin/python scripts/scrape.py boc nsb    # only some
HEADLESS=0 .venv/bin/python scripts/scrape.py boc   # watch the browser
bash scripts/daily.sh                          # full scrape + publish
```

## How the scraper picks the right number

For each bank in `sources.json` it loads the official rate page in headless
Chromium (Brave's engine, since Chrome isn't installed), reads every table row —
including hidden tabs via `textContent` — and maps each row to a tenure
(3M/6M/1Y/2Y). Per-bank config in `sources.json` keeps it accurate:

- `exclude` — row-text fragments that mark a row as NOT the standard product
  (senior, monthly-payout, bulk, etc.). Added on top of `DEFAULT_EXCLUDE`.
- `include` — a row must contain ALL these fragments to count (e.g. `"(lkr)"`).
- `col`     — which numeric column holds the at-maturity rate (`0` first, `-1` last).
- `scrape: false` — disable a site whose layout isn't reliably parseable yet;
  its last-known values are kept and the bank is shown `stale`.

Safety rules baked in: only rates in **4–16% p.a.** are accepted; a bank is
marked `live` only when **all four tenures** are freshly read this run; otherwise
the previous values are kept and the bank stays `stale`. **It never guesses.**

## Coverage

| Rule-scraped live | LLM fallback (`method: llm`) |
|---|---|
| Commercial, BOC, NSB, Sampath, People's, HNB*, LOLC | NTB, Seylan, Pan Asia |

\* HNB's page lists only 3M/6M/12M (no 24-month row); it refreshes those three
and keeps the last-known 2Y.

### Hybrid LLM fallback

NTB, Seylan and Pan Asia don't expose their FD rates in a machine-readable table
(PDF-only / multi-product / no HTML table). For these, the scraper still renders
the page with Selenium, then sends the page text to the Claude API
(`llm_extract`, model `claude-haiku-4-5`) to pull the four standard at-maturity
rates. Same safety rules apply (4–16% band; null tenures kept as last-known).

This needs an API key. Create `.env` in the repo root (gitignored):

```
ANTHROPIC_API_KEY=sk-ant-...
```

Without the key those three banks simply stay `stale` — everything else still
works. Cost is a fraction of a cent per day (three short Haiku calls).
