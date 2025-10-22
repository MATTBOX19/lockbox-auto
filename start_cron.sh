#!/usr/bin/env bash
set -euo pipefail

# start_cron.sh — worker entrypoint for Render
# Runs predictor_auto.py once per day and optionally pushes Output back to GitHub.

# allow fallback to GITHUB_TOKEN if GITHUB_PUSH_TOKEN not defined
: "${GITHUB_PUSH_TOKEN:=$GITHUB_TOKEN}"

cd /opt/render/project/src

# optional: activate the repo virtualenv if present
if [ -f ".venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  . .venv/bin/activate
fi

# configure git identity (local only)
git config user.email "matt@tx-cet.com" || true
git config user.name "LockBox Auto Worker" || true

# main loop: run once and exit (Render restarts worker / or container supervision)
echo "Starting daily predictor run: $(date -u --iso-8601=seconds)"

if ! python predictor_auto.py; then
  echo "❌ predictor_auto.py failed, exiting non-zero"
  exit 1
fi

# Optional: push Output CSVs to GitHub if GITHUB_PUSH_TOKEN is set
if [ -n "${GITHUB_PUSH_TOKEN:-}" ]; then
  echo "Pushing generated CSVs back to GitHub..."
  git remote remove origin 2>/dev/null || true
  git remote add origin "https://${GITHUB_PUSH_TOKEN}@github.com/MATTBOX19/lockbox-auto.git"
  git add Output/*.csv || true
  git commit -m "chore(auto): add latest predictions $(date -u +%F)" || true
  git push origin HEAD:main --quiet || echo "Push failed (check token/permissions)."
else
  echo "No GITHUB_PUSH_TOKEN set — skipping git push."
fi

echo "Run complete: $(date -u --iso-8601=seconds)"
