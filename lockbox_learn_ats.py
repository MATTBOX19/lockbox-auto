#!/usr/bin/env python3
"""
lockbox_learn_ats.py — analyze ATS & OU performance

Reads latest settled predictions, measures model accuracy and ROI,
and writes performance metrics to /Output/metrics.json
"""

import json, pandas as pd
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

def calc_win(row, actual_spread=0):
    try:
        if "ATS_Result" in row and row["ATS_Result"]:
            return 1 if row["ATS_Result"].lower() == "win" else 0
    except:
        pass
    return None

def analyze(file: Path):
    df = pd.read_csv(file)
    df.columns = [c.strip() for c in df.columns]
    total = len(df)
    settled = df[df.get("Settled", False) == True]
    if settled.empty:
        print("⚠️ No settled data to learn from.")
        return None

    win_pct = (settled["ML_Result"].astype(str).str.lower() == "win").mean() * 100
    avg_edge = settled["Edge"].astype(float).mean()
    avg_conf = settled["Confidence"].astype(float).mean()

    roi = ((settled["ML_Result"].astype(str).str.lower() == "win").sum() -
           (settled["ML_Result"].astype(str).str.lower() == "loss").sum()) / max(1, len(settled)) * 100

    summary = {
        "timestamp": datetime.utcnow().isoformat(),
        "file": file.name,
        "games_total": int(total),
        "games_settled": int(len(settled)),
        "win_pct": round(win_pct, 2),
        "avg_edge": round(avg_edge, 3),
        "avg_confidence": round(avg_conf, 3),
        "roi_percent": round(roi, 2)
    }

    print(f"🧠 Learned: Win%={summary['win_pct']} | ROI={summary['roi_percent']}%")
    return summary

def update_metrics(data):
    if not data: return
    metrics = []
    if METRICS_FILE.exists():
        with open(METRICS_FILE) as f:
            try:
                metrics = json.load(f)
            except:
                metrics = []
    metrics.append(data)
    with open(METRICS_FILE, "w") as f:
        json.dump(metrics[-50:], f, indent=2)
    print(f"📈 Updated metrics.json ({len(metrics[-50:])} records)")

if __name__ == "__main__":
    latest = find_latest_settled()
    if latest:
        result = analyze(latest)
        update_metrics(result)
    else:
        print("❌ No settled data found.")
