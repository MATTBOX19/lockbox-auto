#!/bin/bash
while true; do
  echo "🔁 Running daily LockBox predictor..."
  python predictor.py
  git add Output/*.csv || true
  git commit -m "auto-update predictions $(date)" || true
  git push origin main || true
  echo "✅ Sleep 24h before next run..."
  sleep 86400
done
