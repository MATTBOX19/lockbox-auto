#!/usr/bin/env python3
"""
settle_results.py

Skeleton script to settle predictions after games finish.

What it does now:
- Finds the latest Predictions_YYYY-MM-DD_Explained.csv in Output/
- Ensures stable result columns exist: ML_Result, ATS_Result, OU_Result, Settled
- Marks rows as 'NEEDS_SETTLING' for games whose GameTime is in the past (UTC).
- Writes a Settled CSV: Output/Predictions_YYYY-MM-DD_Settled.csv
- Copies the settled CSV to Archive/ for safekeeping.

Future integration:
- Replace the `fetch_game_results_stub()` stub with a call to a sports results API
  (or your own scoring source). The function should return actual outcomes which
  will be written into ML_Result / ATS_Result / OU_Result and set Settled=True.

This script is intentionally non-destructive and reversible.
"""
import pandas as pd
from pathlib import Path
from datetime import datetime, timezone
import sys

ROOT = Path(".")
OUT_DIR = ROOT / "Output"
ARCHIVE = ROOT / "Archive"
ARCHIVE.mkdir(exist_ok=True)

def find_latest_predictions():
    files = sorted(OUT_DIR.glob("Predictions_*_Explained.csv"))
    if not files:
        print("No predictions CSV found in Output/. Exiting.")
        sys.exit(0)
    return files[-1]

def fetch_game_results_stub(row):
    """
    Stub for fetching actual game results.
    Replace this with real API calls. Expected return format:
    {
      "ml_result": "W" or "L" or "PUSH" or None,
      "ats_result": "W" / "L" / "PUSH" / None,
      "ou_result": "W" / "L" / "PUSH" / None
    }
    """
    return {"ml_result": None, "ats_result": None, "ou_result": None}

def iso_to_utc(dt_str):
    try:
        return pd.to_datetime(dt_str, utc=True)
    except Exception:
        return None

def main():
    latest = find_latest_predictions()
    print("Using predictions file:", latest)
    df = pd.read_csv(latest)
    # Normalize column names
    df.columns = [c.strip() for c in df.columns]

    # Add result columns if missing
    for col in ["ML_Result", "ATS_Result", "OU_Result", "Settled"]:
        if col not in df.columns:
            df[col] = ""

    # Parse GameTime and identify games that have started (in the past)
    now = pd.Timestamp.now(tz=timezone.utc)
    df["_GameTime_dt"] = df["GameTime"].apply(iso_to_utc)
    df["_Finished"] = df["_GameTime_dt"].apply(lambda x: bool(x and x <= now))

    # For finished games, attempt to fetch results (stub for now)
    to_settle = df[df["_Finished"] & (df["Settled"] == "")]
    print(f"Games found total={len(df)} finished={len(df[df['_Finished']])} needing_settle={len(to_settle)}")

    if not to_settle.empty:
        for idx, row in to_settle.iterrows():
            # Real implementation: call fetch_game_results(row) and write results
            res = fetch_game_results_stub(row)
            df.at[idx, "ML_Result"] = res.get("ml_result") or ""
            df.at[idx, "ATS_Result"] = res.get("ats_result") or ""
            df.at[idx, "OU_Result"] = res.get("ou_result") or ""
            # mark as needs manual review (not auto-settled) for now
            df.at[idx, "Settled"] = "NEEDS_SETTLING"

    # drop helper cols
    df = df.drop(columns=["_GameTime_dt", "_Finished"], errors="ignore")

    # Save a settled CSV and copy to Archive
    out_settled = OUT_DIR / (latest.stem.replace("_Explained", "_Settled") + latest.suffix)
    df.to_csv(out_settled, index=False)
    archived = ARCHIVE / out_settled.name
    df.to_csv(archived, index=False)
    print("Wrote settled CSV:", out_settled)
    print("Archived copy:", archived)
    print("NOTE: fetch_game_results_stub() is a placeholder — replace with your results API integration.")
    # print quick counts
    settled_count = (df["Settled"] != "").sum()
    print(f"Marked {settled_count} rows as Settled/NEEDS_SETTLING (empty means not finished/no change).")

if __name__ == '__main__':
    main()
