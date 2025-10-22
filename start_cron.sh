#!/usr/bin/env bash
set -euo pipefail

# start_cron.sh — worker entrypoint for Render
# Runs predictor_auto.py once per day and optionally pushes Output back to GitHub.

: "${GITHUB_PUSH_TOKEN:=${GITHUB_TOKEN:-}}"

cd /opt/render/project/src

# activate virtualenv if present
if [ -f ".venv/bin/activate" ]; then
  . .venv/bin/activate
fi

# configure git identity
git config user.email "matt@tx-cet.com" || true
git config user.name "LockBox Auto Worker" || true

echo "Starting daily predictor run: $(date -u --iso-8601=seconds)"

if ! python predictor_auto.py; then
  echo "❌ predictor_auto.py failed"
  exit 1
fi

if [ -n "${GITHUB_PUSH_TOKEN:-}" ]; then
  echo "Pushing generated CSVs back to GitHub..."
  git remote remove origin 2>/dev/null || true
  git remote add origin "https://${GITHUB_PUSH_TOKEN}@github.com/MATTBOX19/lockbox-auto.git"

  # make sure we're up-to-date before committing
  git fetch origin main --depth=1 || true
  git checkout main || git checkout -B main
  git reset --hard origin/main || true

  git add Output/*.csv || true
  git commit -m "chore(auto): add latest predictions $(date -u +%F)" || true
  git pull --rebase origin main || true
  git push origin HEAD:main --force || echo "Push failed (check token/permissions)."
else
  echo "No GITHUB_PUSH_TOKEN set — skipping git push."
fi

echo "Run complete: $(date -u --iso-8601=seconds)"

# keep container alive so Render marks it healthy
while true; do
  sleep 3600
done
