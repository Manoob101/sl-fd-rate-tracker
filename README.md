# 🇱🇰 Sri Lanka FD Rate Tracker

A live Fixed Deposit rate dashboard that refreshes daily from each bank's
official rate page.

```
fd/
├── docs/                     # the deployable static site
│   ├── index.html            # the dashboard (reads data/rates.json)
│   └── data/
│       ├── rates.json        # ← source of truth (current rates)
│       ├── rates.js          # generated shim (for file:// use)
│       └── history.jsonl     # daily snapshots → trend arrows
├── sources.json              # per-bank URLs + scrape rules (exclude/include/col)
├── scripts/
│   ├── scrape.py             # Selenium scraper → updates rates.json
│   ├── build.py              # regenerates shim + appends history
│   ├── serve.py              # local web server for the dashboard
│   ├── daily.sh             # scrape + commit + push (run by launchd)
│   └── com.fd.ratetracker.plist  # launchd schedule (07:00 daily)
├── .venv/                    # python env with selenium (gitignored)
├── UPDATE.md                 # how the daily update works
└── README.md
```

## View it

```bash
python3 scripts/serve.py      # opens http://localhost:8799 (or next free port)
```

Or just double-click `docs/index.html` (it falls back to the `rates.js` shim).

## How updating works

A **Selenium Python scraper** (`scripts/scrape.py`) loads each bank's official
rate page in headless Chromium, reads the FD table (incl. JS-rendered / hidden
tabs via `textContent`), and writes `docs/data/rates.json`. No API key, no Claude
— it runs on its own. See [`UPDATE.md`](UPDATE.md) for the full details and
per-bank tuning options.

- **Scraped live (verified):** Commercial, BOC, NSB, Sampath, People's.
- **Last-known / `stale`:** HNB (page has no 24-month row), Seylan, NTB, Pan Asia,
  LOLC — these have JS-only / consent-walled / ambiguous multi-product layouts and
  are disabled (`scrape: false`) until a per-bank rule is written. They keep their
  last-known values rather than showing a wrong one.

Safety: only 4–16% p.a. values are accepted; a bank goes `live` only when all four
tenures are freshly read; otherwise it stays `stale`. The scraper never guesses.

### Daily schedule (launchd)

```bash
cp scripts/com.fd.ratetracker.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.fd.ratetracker.plist
```

Runs `scripts/daily.sh` at 07:00 local time: scrape → `build.py` → commit → push.
Logs go to `logs/`. Run `bash scripts/daily.sh` any time to do it manually.

## Live site

Hosted free on **GitHub Pages** → **https://manoob101.github.io/sl-fd-rate-tracker/**

- Repo: https://github.com/Manoob101/sl-fd-rate-tracker
- Pages serves the `docs/` folder on the `main` branch (Settings → Pages →
  Source: `main` /docs). GitHub auto-rebuilds on every push — no Actions workflow
  or backend needed.
- The daily scheduled job rewrites `docs/data/rates.json`, runs `build.py`, then
  `git push`es — which redeploys the live site within a minute or two.

## Disclaimer

Rates are indicative and change without notice. Not financial advice — confirm
with the bank before depositing.
