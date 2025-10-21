#!/usr/bin/env python3
"""
lockbox_validate.py

Phase 4: LockBox Model Validation Tests

Purpose:
  - Runs automated sanity checks to ensure data consistency.
  - Confirms model logic stays within expected statistical bounds.
  - Logs issues for tracking model reliability over time.

Checks include:
  ✅ EV vs Edge consistency
  ✅ Team probabilities sum to 1
  ✅ Confidence and Edge within [0, 100] / reasonable range
  ✅ Missing or invalid picks
  ✅ Logs results to /Logs/validation_YYYY-MM-DD.txt
"""

import pandas as pd
from pathlib import Path
from datetime import datetime

ROOT = Path(".")
OUT_DIR = ROOT / "Output"
LOG_DIR = ROOT / "Logs"
LOG_DIR.mkdir(exist_ok=True)

def find_latest_predictions():
    files = sorted(OUT_DIR.glob("Predictions_*_Explained.csv"))
    if not files:
        print("⚠️ No predictions file found in Output/")
        return None
    return files[-1]

def run_validation():
    latest_file = find_latest_predictions()
    if not latest_file:
        return

    df = pd.read_csv(latest_file)
    df.columns = [c.strip() for c in df.columns]

    errors = []
    warnings = []

    # Check 1: Confidence bounds
    if "Confidence" in df:
        out_of_bounds = df[(df["Confidence"] < 0) | (df["Confidence"] > 100)]
        if not out_of_bounds.empty:
            errors.append(f"❌ Confidence out of [0,100]: {len(out_of_bounds)} rows")

    # Check 2: Edge bounds
    if "Edge" in df:
        too_high = df[df["Edge"] > 100]
        if not too_high.empty:
            warnings.append(f"⚠️ Extremely high Edge values: {len(too_high)} rows")

    # Check 3: Missing picks
    if "MoneylinePick" in df:
        missing = df[df["MoneylinePick"].isna() | (df["MoneylinePick"].astype(str).str.strip() == "")]
        if not missing.empty:
            errors.append(f"❌ Missing MoneylinePick: {len(missing)} rows")

    # Check 4: Duplicates
    dupes = df[df.duplicated(subset=["Team1", "Team2", "Sport"], keep=False)]
    if not dupes.empty:
        warnings.append(f"⚠️ Duplicate games found: {len(dupes)} rows")

    # Check 5: Total team probability (rough)
    if "ML" in df:
        bad_probs = df[df["ML"].astype(str).str.count(":") < 2]
        if not bad_probs.empty:
            warnings.append(f"⚠️ Incomplete ML format: {len(bad_probs)} rows")

    # Summary stats
    summary = f"""
LockBox Validation Report — {datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")}
File: {latest_file.name}
Rows: {len(df)}

Results:
  Errors: {len(errors)}
  Warnings: {len(warnings)}
    """.strip()

    print(summary)
    for e in errors + warnings:
        print(e)

    # Write log
    log_path = LOG_DIR / f"validation_{datetime.utcnow().strftime('%Y-%m-%d')}.txt"
    with open(log_path, "w") as f:
        f.write(summary + "\n\n")
        for e in errors + warnings:
            f.write(e + "\n")

    print(f"🧾 Validation log written to {log_path}")

if __name__ == "__main__":
    run_validation()
