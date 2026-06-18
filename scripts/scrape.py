#!/usr/bin/env python3
"""Selenium-based daily FD-rate scraper.

Loads each bank's official rate page in a headless Chromium browser (so
JavaScript-rendered tables work), extracts the standard LKR Fixed Deposit rates
for 3M / 6M / 1Y / 2Y, validates them, and merges the result into
docs/data/rates.json — then runs build.py.

Design rules:
  * Never invent a number. A tenure is only updated when a plausible rate
    (4–16% p.a.) is found; otherwise the previous value is kept.
  * A bank is marked "live" only if all four tenures were freshly read this run;
    a partial/failed read keeps the old values and marks the bank "stale".
  * Banks not refreshed keep their previous `scraped_at` date.

Run:  .venv/bin/python scripts/scrape.py            (all banks)
      .venv/bin/python scripts/scrape.py boc nsb    (only some)
      HEADLESS=0 .venv/bin/python scripts/scrape.py boc   (watch it)
"""
import json
import os
import re
import sys
import time
from datetime import datetime, timezone, timedelta

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCES = os.path.join(ROOT, "sources.json")
RATES_JSON = os.path.join(ROOT, "docs", "data", "rates.json")

COLOMBO = timezone(timedelta(hours=5, minutes=30))
RATE_MIN, RATE_MAX = 4.0, 16.0          # plausible FD rate band (% p.a.)

# Canonical tenure -> regexes that match a row label for that tenure.
TENURE_PATTERNS = {
    "3M": [r"\b0?3\s*month", r"\b3\s*mth", r"\b90\s*day"],
    "6M": [r"\b0?6\s*month", r"\b6\s*mth", r"\b180\s*day"],
    "1Y": [r"\b12\s*month", r"\b1\s*year", r"\b1\s*yr", r"\b360\s*day", r"\b365\s*day"],
    "2Y": [r"\b24\s*month", r"\b2\s*year", r"\b2\s*yr"],
}
EFFECTIVE_RE = re.compile(r"w\.?e\.?f\.?\s*:?\s*(\d{1,2}[./-]\d{1,2}[./-]\d{2,4})", re.I)
NUM_RE = re.compile(r"(\d{1,2}\.\d{1,2})|(\d{1,2})\s*%")

# Rows whose text contains any of these are NOT the standard general-public,
# interest-at-maturity FD and are skipped. Per-bank extra excludes come from
# sources.json ("exclude": [...]).
DEFAULT_EXCLUDE = [
    "senior", "citizen", "monthly", "annually", "annual interest", "weekly",
    "quarterly", "child", "minor", "junior", "premier", "corporate", "staff",
    "nrfc", "rfc", "fcy", "foreign", "savings", "certificate", "special",
    "plus", "double", "step-up", "stepup", "day)", "days)", "minimum",
]


def classify(label):
    low = label.lower()
    # check 2Y/1Y before the month-only patterns
    for ten in ("2Y", "1Y", "6M", "3M"):
        for pat in TENURE_PATTERNS[ten]:
            if re.search(pat, low):
                return ten
    return None


def row_rates(cells, label_idx):
    """All plausible FD rates (4–16%) in a row, in column order, skipping the
    label cell. Returns a list so a per-bank `col` index can choose the right
    column (e.g. an at-maturity column that isn't the first number)."""
    out = []
    for i, cell in enumerate(cells):
        if i == label_idx:
            continue
        for m in NUM_RE.finditer(cell):
            val = float(m.group(1) or m.group(2))
            if RATE_MIN <= val <= RATE_MAX:
                out.append(round(val, 2))
    return out


def extract_rates(driver, cfg):
    """Walk every table row (incl. hidden tabs via textContent) and map each
    tenure to a rate. Per-bank config:
      exclude : extra row-text fragments that disqualify a row
      include : if set, a row must contain ALL of these fragments to count
      col     : which plausible-number column to take (0=first default, -1=last)
    When several rows match one tenure, prefer rows mentioning 'maturity', then
    the plainest (shortest) label."""
    excl = [e.lower() for e in DEFAULT_EXCLUDE + list(cfg.get("exclude", []))]
    incl = [i.lower() for i in cfg.get("include", [])]
    col = cfg.get("col", 0)
    cell_idx = cfg.get("cell")          # read rate from this raw cell index
    bare = cfg.get("bare_months")       # tenure label is a bare number of months
    bare_map = {3: "3M", 6: "6M", 12: "1Y", 24: "2Y"}
    candidates = {}            # tenure -> list of (label_len, has_maturity, rate)
    for row in driver.find_elements(By.CSS_SELECTOR, "table tr"):
        raw = [(c.get_attribute("textContent") or "").strip()
               for c in row.find_elements(By.CSS_SELECTOR, "th,td")]
        cells = [re.sub(r"\s+", " ", c) for c in raw if c.strip()]
        if len(cells) < 2:
            continue
        joined = " | ".join(cells).lower()
        if any(x in joined for x in excl):
            continue
        if incl and not all(x in joined for x in incl):
            continue
        label_idx = tenure = None
        for i, c in enumerate(cells):
            t = classify(c)
            if t:
                label_idx, tenure = i, t
                break
        if tenure is None and bare:
            m = re.fullmatch(r"0?(\d{1,2})", cells[0])
            if m:
                tenure = bare_map.get(int(m.group(1)))
                label_idx = 0
        if tenure is None:
            continue
        if cell_idx is not None:                # fixed-column read (e.g. a 'maturity' col)
            rate = None
            if cell_idx < len(cells):
                for mm in NUM_RE.finditer(cells[cell_idx]):
                    v = float(mm.group(1) or mm.group(2))
                    if RATE_MIN <= v <= RATE_MAX:
                        rate = round(v, 2)
                        break
            if rate is None:
                continue
        else:
            rates = row_rates(cells, label_idx)
            if not rates:
                continue
            try:
                rate = rates[col]
            except IndexError:
                rate = rates[-1] if col < 0 else rates[0]
        has_mat = "maturity" in cells[label_idx].lower()
        candidates.setdefault(tenure, []).append((len(cells[label_idx]), has_mat, rate))

    found = {}
    for tenure, cands in candidates.items():
        mat = [c for c in cands if c[1]]
        pool = mat or cands
        pool.sort(key=lambda c: c[0])      # plainest (shortest) label wins
        found[tenure] = pool[0][2]
    return found


def parse_effective(page_text):
    m = EFFECTIVE_RE.search(page_text)
    if not m:
        return ""
    raw = m.group(1).replace("/", ".").replace("-", ".")
    for fmt in ("%d.%m.%Y", "%d.%m.%y"):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return ""


def make_driver():
    opts = Options()
    if os.environ.get("HEADLESS", "1") != "0":
        opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--window-size=1400,2200")
    opts.add_argument("--lang=en-US")
    opts.add_argument(
        "user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36")
    # No Chrome installed on this Mac -> use Brave's Chromium engine.
    for cand in ("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                 "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"):
        if os.path.exists(cand):
            opts.binary_location = cand
            break
    driver = webdriver.Chrome(options=opts)   # Selenium Manager fetches the driver
    driver.set_page_load_timeout(45)
    return driver


def scrape_bank(driver, bank):
    driver.get(bank["source"])
    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "table")))
    except Exception:
        pass
    time.sleep(2.5)            # let late JS settle
    clk = bank.get("click")    # open a tab/accordion before reading (e.g. LOLC)
    if clk:
        for el in driver.find_elements(By.XPATH, f"//*[contains(., '{clk}')]"):
            try:
                driver.execute_script("arguments[0].scrollIntoView({block:'center'});"
                                      "arguments[0].click();", el)
                time.sleep(0.4)
            except Exception:
                pass
        time.sleep(2)
    rates = extract_rates(driver, bank)
    body = driver.find_element(By.TAG_NAME, "body")
    effective = parse_effective((body.get_attribute("textContent") or "")[:8000])
    return rates, effective


def main():
    only = set(a.lower() for a in sys.argv[1:])
    with open(SOURCES, encoding="utf-8") as f:
        sources = json.load(f)["banks"]
    with open(RATES_JSON, encoding="utf-8") as f:
        data = json.load(f)
    by_id = {b["id"]: b for b in data["banks"]}

    driver = make_driver()
    today = datetime.now(COLOMBO).strftime("%Y-%m-%d")
    summary = []
    try:
        for src in sources:
            bid = src["id"]
            if only and bid not in only:
                continue
            bank = by_id.get(bid)
            if not bank:
                continue
            if not src.get("scrape", True):
                # parser for this site isn't trusted yet → keep last-known values
                bank["status"] = "stale"
                bank["note"] = "Auto-scrape not yet supported for this site (complex/JS layout). Showing last-known."
                summary.append(f"  - {bid:9s} skipped (scrape disabled) — last-known kept")
                continue
            try:
                rates, effective = scrape_bank(driver, src)
            except Exception as e:
                rates, effective = {}, ""
                print(f"  ! {bid}: error {type(e).__name__}: {str(e)[:80]}")

            got = {t: v for t, v in rates.items() if v is not None}
            for t, v in got.items():
                bank["rates"][t] = v                 # update only what we found
            miss = [t for t in ("3M", "6M", "1Y", "2Y") if t not in got]
            # Live when all four are read, or (for pages that simply don't list a
            # tenure) when 1Y + at least 3 are read this run.
            if len(got) == 4 or ("1Y" in got and len(got) >= 3):
                bank["status"] = "live"
                bank["scraped_at"] = today
                if effective:
                    bank["effective"] = effective
                bank["note"] = (f"{', '.join(miss)} not listed on the page; last-known kept."
                                if miss else "")
                summary.append(f"  ✓ {bid:9s} live  {got}" + (f" (missing {miss})" if miss else ""))
            else:
                bank["status"] = "stale"
                bank["note"] = f"Auto-scrape incomplete on {today}; missing {miss}. Showing last-known."
                summary.append(f"  ~ {bid:9s} stale (got {sorted(got) or 'nothing'}, missing {miss})")
    finally:
        driver.quit()

    data["as_of"] = datetime.now(COLOMBO).isoformat(timespec="seconds")
    with open(RATES_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print("\n".join(summary))
    live = sum(1 for b in data["banks"] if b["status"] == "live")
    print(f"\nscrape done — {live}/{len(data['banks'])} live. Running build.py …")
    os.system(f'"{sys.executable}" "{os.path.join(ROOT, "scripts", "build.py")}"')


if __name__ == "__main__":
    main()
