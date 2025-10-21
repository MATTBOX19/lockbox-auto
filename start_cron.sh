#!/usr/bin/env bash
set -euo pipefail

# start_cron.sh
# Runs predictor and (optionally) commits output back to GitHub.
# It expects an env var GITHUB_PUSH_TOKEN (personal access token) if you want automatic push.
# If no token is provided, it will skip push steps.

echo "🔁 Running daily LockBox predictor..."

# run predictor (assumes predictor.py exists and writes to Output/)
python predictor.py || { echo "predictor failed"; exit 1; }

# git identity local to repo (not global)
git config user.email "matt@tx-cet.com" || true
git config user.name "LockBox Auto" || true

# ensure we're on main and have a local repo (Render provides checkout)
git checkout -B main || true

# re-add the origin with token if provided
if [ -n "${GITHUB_PUSH_TOKEN:-}" ]; then
  # use token for push (keeps token out of git history)
  git remote remove origin 2>/dev/null || true
  git remote add origin "https://${GITHUB_PUSH_TOKEN}@github.com/MATTBOX19/lockbox-auto.git"
fi

# add and commit any CSVs
git add Output/*.csv || true
git commit -m "auto-update predictions $(date -u +"%Y-%m-%d %H:%M UTC")" || true

# push only if token set
if [ -n "${GITHUB_PUSH_TOKEN:-}" ]; then
  git push -u origin main --quiet || echo "git push failed"
else
  echo "No GITHUB_PUSH_TOKEN set — skipping git push."
fi

echo "✅ Sleep 24h before next run..."
sleep 86400
