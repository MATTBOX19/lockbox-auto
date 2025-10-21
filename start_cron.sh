#!/bin/bash

while true; do
  echo "🔁 Running daily LockBox predictor..."

  # Run the predictor script
  python predictor.py

  # Configure Git identity and remote
  git config --global user.email "matt@tx-cet.com"
  git config --global user.name "LockBox Auto"

  # Re-add Git remote each run (Render doesn’t persist remotes)
  git remote remove origin 2>/dev/null || true
  git remote add origin https://$GITHUB_TOKEN@github.com/MATTBOX19/lockbox-auto.git

  # Ensure we’re on the correct branch and up to date
  git checkout main || git checkout -b main
  git pull origin main || true

  # Commit and push new predictions
  git add Output/*.csv || true
  git commit -m "auto-update predictions $(date)" || true
  git push origin main || true

  echo "✅ Sleep 24h before next run..."
  sleep 86400
done