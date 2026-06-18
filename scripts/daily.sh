#!/bin/bash
# Daily FD-rate scrape + publish. Run by launchd (see scripts/com.fd.ratetracker.plist).
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
mkdir -p logs
echo "===== $(date '+%Y-%m-%d %H:%M:%S') run start =====" >> logs/scrape.log

# 1. scrape (Selenium) -> updates docs/data/rates.json + runs build.py
./.venv/bin/python scripts/scrape.py >> logs/scrape.log 2>&1

# 2. publish to GitHub Pages if data changed
if ! git diff --quiet -- docs/data; then
  git add docs/data
  git -c commit.gpgsign=false commit -m "rates: $(date +%F)" >> logs/scrape.log 2>&1
  git push >> logs/scrape.log 2>&1 && echo "pushed" >> logs/scrape.log
else
  echo "no data changes — nothing to publish" >> logs/scrape.log
fi
echo "===== run end =====" >> logs/scrape.log
