#!/usr/bin/env python3
"""
lockbox_feedback.py

Phase 9: AI Feedback Trainer
----------------------------

Purpose:
  LockBox learns from its own performance over time.

It automatically:
  - Reads metrics.json for historical accuracy and ROI.
  - Adjusts key model parameters (ADJUST_FACTOR, LOCK_EDGE_THRESHOLD, etc.)
  - Logs parameter changes for traceability.
  - Produces updated predictor_config.json that predictor.py will read.

This makes LockBox self-tuning over time.
"""

import json
import statistics
from datetime import datetime
from pathlib import Path

ROOT = Path(".")
OUT_DIR = ROOT / "Output"
CONFIG_FILE = OUT_DIR / "predictor_config.json"
METRICS_FILE = OUT_DIR / "metrics.json"
LOG_FILE = OUT_DIR / "feedback_log.txt"

# Default parameters (baseline)
params = {
    "ADJUST_FACTOR": 0.35,
    "LOCK_EDGE_THRESHOLD": 0.5,
    "LOCK_CONFIDENCE_THRESHOLD": 51.0,
    "UPSET_EDGE_THRESHOLD": 0.3
}

def load_metrics():
    if METRICS_FILE.exists():
        try:
            with open(METRICS_FILE) as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data[-10:]  # last 10 sessions
        except Exception as e:
            print(f"Error loading metrics: {e}")
    return []

def adaptive_tuning(metrics):
    if not metrics:
        print("No metrics found, using defaults.")
        return params

    win_rates = [m.get("win_pct", 0) for m in metrics if m.get("win_pct")]
    rois = [m.get("roi_percent", 0) for m in metrics if m.get("roi_percent")]
    edges = [m.get("avg_edge", 0) for m in metrics if m.get("avg_edge")]
    confs = [m.get("avg_confidence", 0) for m in metrics if m.get("avg_confidence")]

    avg_win = statistics.mean(win_rates) if win_rates else 50
    avg_roi = statistics.mean(rois) if rois else 0
    avg_edge = statistics.mean(edges) if edges else 0.1
    avg_conf = statistics.mean(confs) if confs else 50.5

    print(f"📊 Historical averages: Win={avg_win:.1f} ROI={avg_roi:.2f}% Edge={avg_edge:.2f} Conf={avg_conf:.1f}")

    new_params = params.copy()

    # Adjust dynamically
    if avg_win > 55 and avg_roi > 5:
        new_params["ADJUST_FACTOR"] = min(0.5, params["ADJUST_FACTOR"] + 0.05)
    elif avg_win < 48:
        new_params["ADJUST_FACTOR"] = max(0.2, params["ADJUST_FACTOR"] - 0.05)

    if avg_roi > 5:
        new_params["LOCK_EDGE_THRESHOLD"] = max(0.4, params["LOCK_EDGE_THRESHOLD"] - 0.05)
    elif avg_roi < 0:
        new_params["LOCK_EDGE_THRESHOLD"] = min(0.6, params["LOCK_EDGE_THRESHOLD"] + 0.05)

    if avg_conf > 52:
        new_params["LOCK_CONFIDENCE_THRESHOLD"] = min(53, params["LOCK_CONFIDENCE_THRESHOLD"] + 0.5)
    elif avg_conf < 50.2:
        new_params["LOCK_CONFIDENCE_THRESHOLD"] = max(50, params["LOCK_CONFIDENCE_THRESHOLD"] - 0.5)

    return new_params

def save_config(updated):
    CONFIG_FILE.write_text(json.dumps(updated, indent=2))
    print(f"✅ Saved new config → {CONFIG_FILE}")

    with open(LOG_FILE, "a") as log:
        log.write(f"[{datetime.utcnow()}] Updated parameters: {json.dumps(updated)}\n")

def run_feedback():
    print("===================================")
    print(" 🔁 LOCKBOX AI FEEDBACK TRAINER ")
    print("===================================")

    metrics = load_metrics()
    updated = adaptive_tuning(metrics)
    save_config(updated)

    print("===================================")
    print("✅ Feedback phase complete.")
    print("===================================")

if __name__ == "__main__":
    run_feedback()
