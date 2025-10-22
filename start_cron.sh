#!/usr/bin/env bash
set -euo pipefail

echo "🔁 Starting persistent LockBox daily predictor loop..."

# Configure git identity
git config user.email "matt@tx-cet.com" || true
git config user.name "LockBox Auto" || true
git checkout -B main || true

# Attach token if available
if [ -n "${GITHUB_PUSH_TOKEN:-}" ]; then
  git remote remove origin 2>/dev/null || true
  git remote add origin "https://${GITHUB_PUSH_TOKEN}@github.com/MATTBOX19/lockbox-auto.git"
fi

# Main loop — runs once per day forever
while true; do
  echo "🔁 Running daily LockBox predictor at $(date -u +"%Y-%m-%d %H:%M UTC")..."
  
  # Run predictor_auto.py (auto fetch + save)
  if ! python predictor_auto.py; then
    echo "⚠️ predictor_auto.py failed — retrying in 1h"
    sleep 3600
    continue
  fi

  # Commit and push
  git add Output/*.csv || true
  git commit -m "auto-update predictions $(date -u +"%Y-%m-%d %H:%M UTC")" || true

  if [ -n "${GITHUB_PUSH_TOKEN:-}" ]; then
    git push -u origin main --quiet || echo "⚠️ git push failed"
  else
    echo "No GITHUB_PUSH_TOKEN set — skipping git push."
  fi

  echo "✅ Sleep 24h before next run..."
  sleep 86400
done
