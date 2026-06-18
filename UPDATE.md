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

## Coverage today

| Scraped live (verified) | Last-known / stale (parser TODO) |
|---|---|
| Commercial, BOC, NSB, Sampath, People's | HNB* , Seylan, NTB, Pan Asia, LOLC |

\* HNB's page only lists 3M/6M/12M (no 24-month row), so it refreshes three
tenures and stays `stale` on 2Y. NTB & Pan Asia render nothing to the scraper
(JS SPA / consent wall); Seylan & LOLC have ambiguous multi-product layouts.
Enable any of them later by writing its `include`/`col`/`exclude` rule and
setting `scrape: true`.
