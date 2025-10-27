#!/usr/bin/env bash
set -euo pipefail

cd /opt/render/project/src
[ -f ".venv/bin/activate" ] && . .venv/bin/activate

LOG_FILE="Output/auto_run_log.txt"
mkdir -p Output

run_cycle() {
  echo "🌅 $(date -u --iso-8601=seconds) — starting" | tee -a "$LOG_FILE"
  python predictor_min.py 2>&1 | tee -a "$LOG_FILE" || true
  echo "✅ $(date -u --iso-8601=seconds) — done" | tee -a "$LOG_FILE"
}

sleep_until_7am() {
  # 7am ET == 12:00 UTC
  now_utc=$(date -u +%s)
  next_7am_utc=$(date -u -d "12:00:00" +%s)
  [ "$now_utc" -ge "$next_7am_utc" ] && next_7am_utc=$(date -u -d "12:00:00 tomorrow" +%s)
  sleep_seconds=$((next_7am_utc - now_utc))
  echo "⏳ sleeping $sleep_seconds seconds to 7am ET…" | tee -a "$LOG_FILE"
  sleep $sleep_seconds
}

# initial run on boot (so you get picks immediately)
run_cycle

# then daily
while true; do
  sleep_until_7am
  run_cycle
done
