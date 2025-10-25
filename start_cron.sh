#!/usr/bin/env bash
set -euo pipefail
# start_cron.sh — daily auto pipeline for LockBox (runs 7 AM ET / 12:00 UTC)

: "${GITHUB_PUSH_TOKEN:=${GITHUB_TOKEN:-}}"
cd /opt/render/project/src
[ -f ".venv/bin/activate" ] && . .venv/bin/activate

git config user.email "matt@tx-cet.com" || true
git config user.name "LockBox Auto Worker" || true

LOG_FILE="Output/auto_run_log.txt"
SUCCESS_FILE="Output/last_success.log"

run_cycle() {
  echo "🌅 Starting daily LockBox cycle: $(date -u --iso-8601=seconds)" | tee -a "$LOG_FILE"

  # 0) refresh live stats
  python fetchers/fetch_apisports_live.py >> "$LOG_FILE" 2>&1 || echo "⚠️ fetch_apisports_live.py failed" | tee -a "$LOG_FILE"

  # 1) generate picks
  python predictor_auto.py >> "$LOG_FILE" 2>&1 || { echo "❌ predictor_auto.py failed" | tee -a "$LOG_FILE"; return 1; }

  # 2) settle completed games
  python settle_results.py >> "$LOG_FILE" 2>&1 || echo "⚠️ settle_results skipped" | tee -a "$LOG_FILE"

  # 3) learn from ATS/OU
  python lockbox_learn_ats.py >> "$LOG_FILE" 2>&1 || echo "⚠️ lockbox_learn_ats skipped" | tee -a "$LOG_FILE"

  # 4) learn global metrics
  python lockbox_learn.py >> "$LOG_FILE" 2>&1 || echo "⚠️ lockbox_learn skipped" | tee -a "$LOG_FILE"

  # 5) merge with latest stats
  python lockbox_learn_stats.py >> "$LOG_FILE" 2>&1 || echo "⚠️ lockbox_learn_stats skipped" | tee -a "$LOG_FILE"

  # 6) push artifacts to GitHub
  if [ -n "${GITHUB_PUSH_TOKEN:-}" ]; then
    echo "📤 Pushing new data..." | tee -a "$LOG_FILE"
    git fetch origin main --depth=1 || true
    git checkout main || git checkout -B main
    git reset --hard origin/main || true
    git add Output/*.csv Output/*.json || true
    git commit -m "chore(auto): daily LockBox update $(date -u +%F)" || true
    git pull --rebase origin main || true
    git push origin HEAD:main --force || echo "Push failed (non-fatal)" | tee -a "$LOG_FILE"
  else
    echo "No GitHub token — skipping push." | tee -a "$LOG_FILE"
  fi

  echo "✅ LockBox cycle complete: $(date -u --iso-8601=seconds)" | tee -a "$LOG_FILE"
  date -u --iso-8601=seconds > "$SUCCESS_FILE"
  echo "------------------------------------------------------------" | tee -a "$LOG_FILE"
}

sleep_until_7am() {
  now_utc=$(date -u +%s)
  next_7am_utc=$(date -u -d "12:00:00" +%s)
  [ "$now_utc" -ge "$next_7am_utc" ] && next_7am_utc=$(date -u -d "12:00:00 tomorrow" +%s)
  sleep_seconds=$((next_7am_utc - now_utc))
  echo "⏳ Sleeping $sleep_seconds seconds until 7 AM ET (12:00 UTC)..." | tee -a "$LOG_FILE"
  sleep $sleep_seconds
}

# loop forever
while true; do
  sleep_until_7am
  run_cycle || echo "⚠️ cycle finished with errors" | tee -a "$LOG_FILE"
done
