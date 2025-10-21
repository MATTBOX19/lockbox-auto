#!/usr/bin/env bash
set -euo pipefail

echo "🔁 Running daily LockBox predictor..."

# Run predictor (assumes predictor.py exists and writes to Output/)
if ! python predictor.py; then
  echo "predictor.py failed; check logs"
  sleep 3600
  exit 1
fi

# configure git identity locally (not global)
git config user.email "matt@tx-cet.com" || true
git config user.name "LockBox Auto" || true
git checkout -B main || true

# if GITHUB_PUSH_TOKEN provided, attach token to remote to push
if [ -n "${GITHUB_PUSH_TOKEN:-}" ]; then
  git remote remove origin 2>/dev/null || true
  git remote add origin "https://${GITHUB_PUSH_TOKEN}@github.com/MATTBOX19/lockbox-auto.git"
fi

# add CSVs and commit
git add Output/*.csv || true
git commit -m "auto-update predictions $(date -u +"%Y-%m-%d %H:%M UTC")" || true

# push if token is present
if [ -n "${GITHUB_PUSH_TOKEN:-}" ]; then
  git push -u origin main --quiet || echo "git push failed"
else
  echo "No GITHUB_PUSH_TOKEN set — skipping git push."
fi

echo "✅ Sleep 24h before next run..."
sleep 86400
