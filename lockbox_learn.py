#!/usr/bin/env python3
"""
lockbox_learn.py — Pro-grade adaptive learning for LockBox
Analyzes settled predictions and logs ML / ATS / OU accuracy + ROI.
Outputs → /Output/metrics.json
"""

import pandas as pd, json
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

def calc_result_stats(df, col_result):
    """Return win/loss/push counts and pct for given result column."""
    if col_result not in df.columns:
        return {"wins":0,"losses":0,"pushes":0,"win_pct":0.0}
    vals = df[col_result].astype(str).str.lower()
    wins = (vals == "win").sum()
    losses = (vals == "loss").sum()
    pushes = (vals == "push").sum()
    total = wins + losses
    win_pct = round((wins / max(1,total)) * 100, 2)
    roi = round(((wins*1) - (losses*1)) / max(1,total) * 100, 2)
    return {
        "wins": int(wins),
        "losses": int(losses),
        "pushes": int(pushes),
        "win_pct": win_pct,
        "roi_percent": roi
    }

def analyze_settled(file: Path):
    df = pd.read_csv(file)
    df.columns = [c.strip() for c in df.columns]

    settled = df[df["Settled"].astype(str).str.lower().isin(["true","yes","settled","needs_settling"])]
    if settled.empty:
        print("No settled games yet.")
        return None

    metrics = {
        "timestamp": datetime.utcnow().isoformat(),
        "file": file.name,
        "games_total": int(len(df)),
        "games_settled": int(len(settled)),
        "avg_edge": round(float(df.get("Edge",0).mean()),3) if "Edge" in df else 0,
        "avg_confidence": round(float(df.get("Confidence",0).mean()),3) if "Confidence" in df else 0
    }

    # compute ML / ATS / OU stats
    for key,label in [("ML_Result","ml"),("ATS_Result","ats"),("OU_Result","ou")]:
        res = calc_result_stats(settled, key)
        metrics[f"{label}_wins"] = res["wins"]
        metrics[f"{label}_losses"] = res["losses"]
        metrics[f"{label}_pushes"] = res["pushes"]
        metrics[f"{label}_win_pct"] = res["win_pct"]
        metrics[f"{label}_roi_percent"] = res["roi_percent"]

    print(
        f"🧠 Learned from {metrics['games_settled']} games — "
        f"ML {metrics['ml_win_pct']}% | ATS {metrics['ats_win_pct']}% | OU {metrics['ou_win_pct']}%"
    )
    return metrics

def update_metrics(new_data):
    metrics = []
    if METRICS_FILE.exists():
        try:
            with open(METRICS_FILE) as f:
                metrics = json.load(f)
                if not isinstance(metrics,list):
                    metrics=[metrics]
        except Exception:
            metrics=[]
    metrics.append(new_data)
    with open(METRICS_FILE,"w") as f:
        json.dump(metrics[-60:],f,indent=2)
    print(f"📈 Updated metrics.json ({len(metrics[-60:])} sessions saved)")

if __name__ == "__main__":
    latest = find_latest_settled()
    if latest:
        res = analyze_settled(latest)
        if res: update_metrics(res)
    else:
        print("❌ No settled data found. Run settle_results.py first.")
