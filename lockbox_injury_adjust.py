#!/usr/bin/env python3
"""
lockbox_injury_adjust.py — Phase 8: Injury & News Dampening System
Reads latest predictions, fetches injury news, adjusts confidence accordingly.
Outputs: Output/Predictions_latest_InjuryAdjusted.csv
"""

import os, requests, pandas as pd
from pathlib import Path
from datetime import datetime, timezone

OUT_DIR = Path("Output")
LATEST_FILE = OUT_DIR / "Predictions_latest_Explained.csv"
ADJ_FILE = OUT_DIR / "Predictions_latest_InjuryAdjusted.csv"

# ✅ you can plug in other APIs later
SPORTSIO_KEY = os.getenv("SPORTSIO_KEY") or os.getenv("ODDS_API_KEY")
INJURY_URL = "https://api.sportsdata.io/v4/nfl/scores/json/Injuries"

# base weighting for key position impact
POSITION_WEIGHTS = {
    "QB": 0.20, "RB": 0.10, "WR": 0.08, "TE": 0.06,
    "K": 0.03, "LB": 0.04, "CB": 0.04, "S": 0.04,
    "DL": 0.05, "OL": 0.05, "DE": 0.05, "T": 0.05
}

def fetch_injury_data():
    try:
        r = requests.get(INJURY_URL, headers={"Ocp-Apim-Subscription-Key": SPORTSIO_KEY}, timeout=10)
        if r.status_code != 200:
            print(f"⚠️ Injury API error {r.status_code}")
            return {}
        data = r.json()
        team_impacts = {}
        for item in data:
            team = item.get("Team")
            pos = item.get("Position")
            status = str(item.get("InjuryStatus","")).lower()
            if not team or not pos: continue
            if "out" in status or "doubt" in status or "questionable" in status:
                impact = POSITION_WEIGHTS.get(pos, 0.03)
                team_impacts[team] = team_impacts.get(team, 0) + impact
        print(f"🩺 Retrieved {len(team_impacts)} team injury ratings")
        return team_impacts
    except Exception as e:
        print("⚠️ Injury fetch error:", e)
        return {}

def main():
    if not LATEST_FILE.exists():
        print("❌ No predictions file found to adjust.")
        return

    df = pd.read_csv(LATEST_FILE)
    if df.empty:
        print("❌ No data found in predictions file.")
        return

    print(f"📘 Loaded {len(df)} predictions")
    injury_map = fetch_injury_data()
    if not injury_map:
        print("⚠️ No injury data — skipping adjustment.")
        df.to_csv(ADJ_FILE, index=False)
        return

    df["AdjustedConfidence"] = df["Confidence"]
    adj_count = 0

    for idx, row in df.iterrows():
        for team, impact in injury_map.items():
            text = str(row.get("BestPick","")) + str(row.get("ML","")) + str(row.get("ATS",""))
            if team in text:
                old = df.at[idx, "AdjustedConfidence"]
                new = max(0, old * (1 - impact))
                df.at[idx, "AdjustedConfidence"] = round(new, 2)
                df.at[idx, "Reason"] = str(row.get("Reason","")) + f" | Injury-adjusted (-{int(impact*100)}%)"
                adj_count += 1

    df.to_csv(ADJ_FILE, index=False)
    print(f"✅ Injury-adjusted file saved: {ADJ_FILE}")
    print(f"🧩 Adjusted {adj_count} picks for injury impact")

if __name__ == "__main__":
    main()
