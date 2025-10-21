while true; do
  echo "🔁 Running daily LockBox predictor..."
  python predictor.py
  git config --global user.email "matt@tx-cet.com"
  git config --global user.name "LockBox Auto"
  git remote set-url origin https://github.com/MATTBOX19/lockbox-auto.git
  git add Output/*.csv || true
  git commit -m "auto-update predictions $(date)" || true
  git push origin main || true
  echo "✅ Sleep 24h before next run..."
  sleep 86400
done
