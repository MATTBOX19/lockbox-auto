#!/usr/bin/env python3
"""
lockbox_dashboard.py

Phase 3: Top 5 Bets + Confidence Dashboard

This script merges predictions, settled results, and learned metrics
to produce:
  - Top 5 bets by (Confidence × Edge)
  - Model performance stats (Win %, ROI, Avg Edge/Conf)
  - A JSON dashboard file consumed by LockBox Web

Output:
  /Output/dashboard.json
"""

import json
import pandas as pd
from pathlib import Path
from datetime import datetime

ROOT = Path(".")
OUT_DIR = ROOT / "Output"
LEARN_FILE = OUT_DIR / "metrics.json"

def load_latest_predictions():
    """Load most recent predictions file."""
    files = sorted(OUT_DIR.glob("Predictions_*_Explained.csv"))
    if not files:
        print("⚠️ No predictions CSV found.")
        return pd.DataFrame()
    latest = files[-1]
    print(f"📘 Using {latest.name}")
    df = pd.read_csv(latest)
    # Normalize column names
    df.columns = [c.strip() for c in df.columns]
    return df

def load_metrics():
    """Load learning metrics if available."""
    if LEARN_FILE.exists():
        with open(LEARN_FILE) as f:
            return json.load(f)
    return {"total_picks": 0, "wins": 0, "roi": 0.0}

def compute_top5(df):
    """Compute Top 5 bets by (Edge × Confidence)."""
    if df.empty or "Edge" not in df or "Confidence" not in df:
        return []
    df["score"] = df["Edge"].astype(float) * df["Confidence"].astype(float)
    top5 = (
        df.sort_values("score", ascending=False)
          .head(5)
          .to_dict(orient="records")
    )
    return [
        {
            "Sport": r.get("Sport", ""),
            "Teams": f"{r.get('Team1', '')} vs {r.get('Team2', '')}",
            "Pick": r.get("MoneylinePick", ""),
            "Confidence": r.get("Confidence", ""),
            "Edge": r.get("Edge", ""),
            "LockEmoji": r.get("LockEmoji", ""),
            "UpsetEmoji": r.get("UpsetEmoji", ""),
        }
        for r in top5
    ]

def build_dashboard():
    df = load_latest_predictions()
    metrics = load_metrics()
    if df.empty:
        print("❌ No data to build dashboard.")
        return

    top5 = compute_top5(df)
    avg_edge = round(df["Edge"].astype(float).mean(), 2) if "Edge" in df else 0
    avg_conf = round(df["Confidence"].astype(float).mean(), 2) if "Confidence" in df else 0
    total = len(df)
    locks = df["LockEmoji"].astype(str).str.strip().astype(bool).sum() if "LockEmoji" in df else 0

    dashboard = {
        "updated": datetime.utcnow().isoformat(),
        "summary": {
            "total_predictions": total,
            "locks": int(locks),
            "avg_edge": avg_edge,
            "avg_confidence": avg_conf,
        },
        "metrics": metrics,
        "top5_bets": top5,
    }

    out_path = OUT_DIR / "dashboard.json"
    with open(out_path, "w") as f:
        json.dump(dashboard, f, indent=2)

    print(f"✅ Dashboard written to {out_path} (Top5={len(top5)})")

if __name__ == "__main__":
    build_dashboard()
