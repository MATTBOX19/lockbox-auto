#!/usr/bin/env python3
"""
lockbox_train.py

Phase 7: Unified Trainer Loop (LockBox AutoCycle)

Purpose:
  - Runs the full LockBox lifecycle in one call:
      1️⃣ Generate new predictions
      2️⃣ Settle previous results
      3️⃣ Analyze technical/AI factors
      4️⃣ Learn from outcomes
      5️⃣ Log summaries to /Logs/training_*.txt

This is the heartbeat of the LockBox AI model.
"""

import subprocess
from pathlib import Path
from datetime import datetime

ROOT = Path(".")
OUT_DIR = ROOT / "Output"
LOG_DIR = ROOT / "Logs"
LOG_DIR.mkdir(exist_ok=True)

PHASES = [
    ("Predictor", ["python", "predictor.py"]),
    ("Settler", ["python", "settle_results.py"]),
    ("Analyzer", ["python", "lockbox_analyze.py"]),
    ("Learner", ["python", "lockbox_learn.py"]),
    ("Validator", ["python", "lockbox_validate.py"])
]

def run_phase(name, cmd):
    print(f"\n🚀 Running {name} phase ...")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        print(result.stdout.strip())
        if result.stderr.strip():
            print(f"⚠️ {name} stderr:\n{result.stderr.strip()}")
        return result.stdout.strip()
    except Exception as e:
        print(f"❌ {name} failed: {e}")
        return str(e)

def run_cycle():
    print("===================================")
    print(" 🔁 LOCKBOX UNIFIED TRAINER START ")
    print("===================================")
    print(datetime.utcnow().strftime("UTC Time: %Y-%m-%d %H:%M:%S"))
    print()

    all_logs = []
    for name, cmd in PHASES:
        log = run_phase(name, cmd)
        all_logs.append(f"=== {name} ===\n{log}\n")

    summary = "\n\n".join(all_logs)
    log_path = LOG_DIR / f"training_{datetime.utcnow().strftime('%Y-%m-%d_%H%M')}.txt"
    log_path.write_text(summary)

    print("\n===================================")
    print(f"✅ Training cycle complete. Log saved to {log_path}")
    print("===================================")

if __name__ == "__main__":
    run_cycle()
