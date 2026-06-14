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
├── sources.json              # per-bank URLs + fetch method
├── scripts/
│   ├── build.py              # regenerates shim + appends history
│   └── serve.py              # local web server for the dashboard
├── UPDATE.md                 # the daily scrape recipe (run by Claude)
└── README.md
```

## View it

```bash
python3 scripts/serve.py      # opens http://localhost:8799 (or next free port)
```

Or just double-click `docs/index.html` (it falls back to the `rates.js` shim).

## How updating works

Extraction is **Claude-powered** (chosen for robustness — half the bank sites are
JavaScript-rendered or bot-protected and can't be parsed with plain regex):

- 5 banks (ComBank, Seylan, People's, BOC, NSB) are fetchable directly via
  `WebFetch` and show **live** rates scraped today.
- 5 banks (HNB, Sampath, LOLC, Pan Asia, NTB) block automated fetches
  (403/503/JS-only). They show last-known values flagged **stale**, and are
  refreshed through a browser-based fetch (Claude-in-Chrome) during the daily run.

The daily job follows [`UPDATE.md`](UPDATE.md): fetch each source → update
`docs/data/rates.json` → `python3 scripts/build.py`.

### Schedule the daily run

In Claude Code, run:

```
/schedule every day at 7am, follow the recipe in /Users/lasithmanuranga/fd/UPDATE.md
```

That creates a cron cloud agent that updates the data each morning. (You can also
run the recipe manually any time by pasting `UPDATE.md` into a session.)

## Deploy to the web (later)

`docs/` is a self-contained static folder — drop it on Vercel / Netlify / GitHub
Pages. Point the host's root at `docs/`. The scheduled agent's last step commits
`docs/data/` and pushes, which triggers a redeploy. No backend required.

## Disclaimer

Rates are indicative and change without notice. Not financial advice — confirm
with the bank before depositing.
