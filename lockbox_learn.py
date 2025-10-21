#!/usr/bin/env python3
"""
lockbox_learn.py

LockBox AI Learning Core
------------------------
Phase 2: Introduces historical performance tracking, evaluation, and
basic adaptive learning logic for LockBox.

Functions:
- load_recent_predictions(): Loads the most recent _Settled.csv or _Explained.csv.
- evaluate_predictions(): Scores results vs. model edge & confidence.
- update_learning_metrics(): Updates rolling performance metrics (ROI, accuracy).
- persist_metrics(): Saves to metrics.json for future calibration.
"""

import os
import json
import pandas as pd
from pathlib import Path
from datetime import datetime

# === PATHS ===
ROOT = Path(".")
OUT_DIR = ROOT / "Output"
ARCHIVE_DIR = ROOT / "Archive"
METRICS_FILE = ROOT / "metrics.json"

# === CONFIG ===
RESULT_COLS = ["ML_Result", "ATS_Result", "OU_Result"]
EVAL_COLUMNS = ["Edge", "Confidence"]
DEFAULT_METRICS = {
    "total_picks": 0,
    "wins": 0,
    "losses": 0,
    "pushes": 0,
    "roi": 0.0,
    "avg_edge": 0.0,
    "avg_confidence": 0.0,
    "accuracy": 0.0,
    "last_updated": None,
}

# === LOAD DATA ===
def load_recent_predictions():
    files = sorted(OUT_DIR.glob("Predictions_*_Settled.csv"), reverse=True)
    if not files:
        files = sorted(OUT_DIR.glob("Predictions_*_Explained.csv"), reverse=True)
    if not files:
        print("❌ No predictions found in Output/.")
        return None
    latest = files[0]
    print(f"📘 Using {latest.name}")
    df = pd.read_csv(latest)
    return df

# === EVALUATE RESULTS ===
def evaluate_predictions(df: pd.DataFrame):
    df = df.copy()
    df["ResultFlag"] = "UNKNOWN"

    if not all(col in df.columns for col in RESULT_COLS):
        print("⚠️ Missing result columns; returning empty evaluation.")
        return df

    for i, row in df.iterrows():
        ml_result = str(row.get("ML_Result", "")).upper().strip()
        if ml_result in ["WIN", "1", "TRUE"]:
            df.at[i, "ResultFlag"] = "WIN"
        elif ml_result in ["LOSS", "0", "FALSE"]:
            df.at[i, "ResultFlag"] = "LOSS"
        elif ml_result == "PUSH":
            df.at[i, "ResultFlag"] = "PUSH"

    win_rate = (df["ResultFlag"] == "WIN").mean()
    avg_edge = df["Edge"].mean() if "Edge" in df else 0.0
    avg_conf = df["Confidence"].mean() if "Confidence" in df else 0.0
    print(f"✅ Evaluation: WinRate={win_rate:.3f}, AvgEdge={avg_edge:.2f}, AvgConf={avg_conf:.2f}")
    return df

# === UPDATE METRICS ===
def update_learning_metrics(df: pd.DataFrame):
    if not METRICS_FILE.exists():
        metrics = DEFAULT_METRICS.copy()
    else:
        with open(METRICS_FILE, "r") as f:
            metrics = json.load(f)

    new_wins = (df["ResultFlag"] == "WIN").sum()
    new_losses = (df["ResultFlag"] == "LOSS").sum()
    new_pushes = (df["ResultFlag"] == "PUSH").sum()
    new_total = new_wins + new_losses + new_pushes
    if new_total == 0:
        print("⚠️ No settled results yet; skipping learning update.")
        return metrics

    metrics["total_picks"] += new_total
    metrics["wins"] += new_wins
    metrics["losses"] += new_losses
    metrics["pushes"] += new_pushes
    metrics["avg_edge"] = float(df["Edge"].mean())
    metrics["avg_confidence"] = float(df["Confidence"].mean())
    metrics["accuracy"] = metrics["wins"] / max(metrics["total_picks"], 1)
    metrics["roi"] = round((metrics["wins"] - metrics["losses"]) / max(metrics["total_picks"], 1), 3)
    metrics["last_updated"] = datetime.utcnow().isoformat()

    with open(METRICS_FILE, "w") as f:
        json.dump(metrics, f, indent=2)

    print(f"📈 Updated metrics: {metrics}")
    return metrics

# === MAIN ===
def main():
    df = load_recent_predictions()
    if df is None or df.empty:
        return
    evaluated = evaluate_predictions(df)
    update_learning_metrics(evaluated)

if __name__ == "__main__":
    main()
