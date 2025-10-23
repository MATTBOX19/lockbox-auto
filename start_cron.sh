#!/usr/bin/env bash
set -euo pipefail
# start_cron.sh — daily auto pipeline for LockBox

: "${GITHUB_PUSH_TOKEN:=${GITHUB_TOKEN:-}}"
cd /opt/render/project/src

if [ -f ".venv/bin/activate" ]; then
  . .venv/bin/activate
fi

git config user.email "matt@tx-cet.com" || true
git config user.name "LockBox Auto Worker" || true

echo "🌅 Starting daily LockBox cycle: $(date -u --iso-8601=seconds)"

python predictor_auto.py || { echo "❌ predictor_auto.py failed"; exit 1; }
python settle_results.py || echo "⚠️ settle_results skipped"
python lockbox_learn_ats.py || echo "⚠️ lockbox_learn_ats skipped"
python lockbox_learn.py || echo "⚠️ lockbox_learn skipped"

if [ -n "${GITHUB_PUSH_TOKEN:-}" ]; then
  echo "📤 Pushing new data..."
  git fetch origin main --depth=1 || true
  git checkout main || git checkout -B main
  git reset --hard origin/main || true
  git add Output/*.csv Output/metrics.json || true
  git commit -m "chore(auto): daily LockBox update $(date -u +%F)" || true
  git pull --rebase origin main || true
  git push origin HEAD:main --force || echo "Push failed"
else
  echo "No GitHub token — skipping push."
fi

echo "✅ LockBox cycle complete: $(date -u --iso-8601=seconds)"
while true; do sleep 3600; done
