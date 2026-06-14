# Daily FD-rate update recipe

This is the instruction set the scheduled Claude Code agent runs once per day to
refresh the dashboard. (You can also just paste it into a Claude Code session.)

## Goal
Update `site/data/rates.json` with today's Fixed Deposit rates for every bank in
`sources.json`, then run the build step. Be accurate; never invent a number.

## Steps

1. Read `sources.json` for the list of banks, their official rate URLs, and the
   `method` hint (`fetch` vs `browser`).

2. For each bank, get the **standard / general-public LKR Fixed Deposit** rates,
   **interest paid at maturity**, for tenures **3M, 6M, 1Y (12mo), 2Y (24mo)**,
   plus the **minimum deposit**. Ignore savings, loan, card, FCY and senior /
   bulk / special-product rates.

   - `method: fetch`  → use the **WebFetch** tool on the `source` URL.
   - `method: browser` → these sites (HNB, Sampath, LOLC, Pan Asia, NTB) block
     plain fetches (403/503) or render rates with JavaScript. Use the
     **Claude-in-Chrome** MCP: navigate to the `source` URL, read the rendered
     page text, and extract the FD table. If Chrome is unavailable, leave that
     bank's rates unchanged and keep its `status` as `stale`.

3. For each bank, in `site/data/rates.json`:
   - If you got fresh numbers: update `rates`, set `status:"live"`,
     `scraped_at` = today (YYYY-MM-DD), set `effective` if the page shows a
     "w.e.f." date, and clear stale notes.
   - If you could **not** get numbers: leave `rates` as-is, set `status:"stale"`,
     and keep `scraped_at` at the last successful date. **Do not guess.**
   - Sanity check: FD rates for these banks are realistically ~5–14% p.a. Reject
     anything outside that band (you probably grabbed a loan/card rate).

4. Set the top-level `as_of` to the current ISO timestamp (`+05:30`, Colombo).

5. Run the build step so the dashboard picks it up and history is recorded:

   ```bash
   python3 scripts/build.py
   ```

6. (When deployed) commit & push so the static host redeploys:

   ```bash
   git add site/data && git commit -m "rates: $(date +%F)" && git push
   ```

## Notes
- The dashboard reads `site/data/rates.json` (live) and falls back to the
  generated `site/data/rates.js` shim for `file://` use. `build.py` regenerates
  the shim and appends a dated snapshot to `site/data/history.jsonl` (used for
  the up/down trend arrows).
- One snapshot per day; re-running the same day overwrites that day's entry.
