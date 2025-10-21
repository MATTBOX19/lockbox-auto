#!/usr/bin/env python3
"""
lockbox_learn.py

Phase 6: LockBox Adaptive Learning Feedback

Purpose:
  - Reads Settled results to measure model accuracy and ROI.
  - Computes rolling performance metrics and saves them to metrics.json.
  - Feeds these back into LockBox Dashboard and Predictor tuning.

Outputs:
  /Output/metrics.json
"""

import pandas as pd
import json
from pathlib import Path
from datetime import datetime

ROOT = Path(".")
OUT_DIR = ROOT / "Output"
METRICS_FILE = OUT_DIR / "metrics.json"

def find_latest_settled():
    files = sorted(OUT_DIR.glob("Predictions_*_Settled.csv"))
    if not files:
        print("⚠️ No settled files found.")
        return None
    return files[-1]

def analyze_settled(file: Path):
    df = pd.read_csv(file)
    df.columns = [c.strip() for c in df.columns]
    if "ML_Result" not in df:
        print("⚠️ No ML_Result column found — skipping.")
        return None

    total = len(df)
    settled = df[df["Settled"].astype(str).str.lower() == "true"]
    if settled.empty:
        print("No settled games yet.")
        return None

    wins = (settled["ML_Result"].astype(str).str.lower() == "win").sum()
    losses = (settled["ML_Result"].astype(str).str.lower() == "loss").sum()

    win_pct = round((wins / max(1, wins + losses)) * 100, 2)
    avg_edge = round(df["Edge"].astype(float).mean(), 3) if "Edge" in df else 0
    avg_conf = round(df["Confidence"].astype(float).mean(), 3) if "Confidence" in df else 0

    roi = round(((wins * 1) - (losses * 1)) / max(1, wins + losses) * 100, 2)

    summary = {
        "timestamp": datetime.utcnow().isoformat(),
        "file": file.name,
        "games_total": int(total),
        "games_settled": int(len(settled)),
        "wins": int(wins),
        "losses": int(losses),
        "win_pct": win_pct,
        "avg_edge": avg_edge,
        "avg_confidence": avg_conf,
        "roi_percent": roi
    }

    print(f"✅ Learned from {len(settled)} games — Win%={win_pct} | ROI={roi}%")
    return summary

def update_metrics(new_data):
    """Merge and keep rolling performance history."""
    metrics = []
    if METRICS_FILE.exists():
        with open(METRICS_FILE) as f:
            metrics = json.load(f)
            if not isinstance(metrics, list):
                metrics = [metrics]

    metrics.append(new_data)
    with open(METRICS_FILE, "w") as f:
        json.dump(metrics[-30:], f, indent=2)  # keep last 30 sessions

    print(f"🧠 Metrics updated → {METRICS_FILE} ({len(metrics[-30:])} sessions saved)")

if __name__ == "__main__":
    latest = find_latest_settled()
    if latest:
        result = analyze_settled(latest)
        if result:
            update_metrics(result)
    else:
        print("❌ No settled data found. Run settle_results.py first.")
