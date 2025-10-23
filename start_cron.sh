#!/usr/bin/env bash
set -euo pipefail
# start_cron.sh — daily auto pipeline for LockBox

: "${GITHUB_PUSH_TOKEN:=${GITHUB_TOKEN:-}}"
cd /opt/render/project/src

# activate venv if present
[ -f ".venv/bin/activate" ] && . .venv/bin/activate

# git identity
git config user.email "matt@tx-cet.com" || true
git config user.name "LockBox Auto Worker" || true

run_cycle() {
  echo "🌅 Starting daily LockBox cycle: $(date -u --iso-8601=seconds)"

  # 1) generate picks
  python predictor_auto.py || { echo "❌ predictor_auto.py failed"; return 1; }

  # 2) settle completed games (safe to skip if none)
  python settle_results.py || echo "⚠️ settle_results skipped"

  # 3) learn from ATS/OU (safe to skip if script not present)
  python lockbox_learn_ats.py || echo "⚠️ lockbox_learn_ats skipped"

  # 4) learn global metrics (safe to skip if no settled file yet)
  python lockbox_learn.py || echo "⚠️ lockbox_learn skipped"

  # 5) push artifacts back to GitHub (optional)
  if [ -n "${GITHUB_PUSH_TOKEN:-}" ]; then
    echo "📤 Pushing new data..."
    git fetch origin main --depth=1 || true
    git checkout main || git checkout -B main
    git reset --hard origin/main || true
    git add Output/*.csv Output/metrics.json || true
    git commit -m "chore(auto): daily LockBox update $(date -u +%F)" || true
    git pull --rebase origin main || true
    git push origin HEAD:main --force || echo "Push failed (non-fatal)"
  else
    echo "No GitHub token — skipping push."
  fi

  echo "✅ LockBox cycle complete: $(date -u --iso-8601=seconds)"
}

# run immediately once, then every 24h
while true; do
  run_cycle || echo "⚠️ cycle finished with errors"
  sleep 86400
done
