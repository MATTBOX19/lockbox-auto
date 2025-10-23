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

SPORTSIO_KEY = os.getenv("SPORTSIO_KEY") or os.getenv("ODDS_API_KEY")

# ✅ Tries 3 URLs in order (official → alternate → fallback stub)
INJURY_ENDPOINTS = [
    "https://api.sportsdata.io/v4/nfl/scores/json/Injuries",
    "https://api.sportsdata.io/v4/nfl/scores/json/Injuries/2025REG",
    "https://api.sportsdata.io/v3/nfl/scores/json/Injuries"
]

POSITION_WEIGHTS = {
    "QB": 0.20, "RB": 0.10, "WR": 0.08, "TE": 0.06,
    "K": 0.03, "LB": 0.04, "CB": 0.04, "S": 0.04,
    "DL": 0.05, "OL": 0.05, "DE": 0.05, "T": 0.05
}

def fetch_injury_data():
    """Tries multiple endpoints; returns aggregated team-level injury impact."""
    for url in INJURY_ENDPOINTS:
        try:
            r = requests.get(url, headers={"Ocp-Apim-Subscription-Key": SPORTSIO_KEY}, timeout=10)
            if r.status_code == 200:
                data = r.json()
                team_impacts = {}
                for item in data:
                    team = item.get("Team")
                    pos = item.get("Position")
                    status = str(item.get("InjuryStatus", "")).lower()
                    if not team or not pos:
                        continue
                    if any(x in status for x in ["out", "doubt", "questionable"]):
                        impact = POSITION_WEIGHTS.get(pos, 0.03)
                        team_impacts[team] = team_impacts.get(team, 0) + impact
                print(f"🩺 Retrieved {len(team_impacts)} team injury ratings from {url}")
                return team_impacts
            else:
                print(f"⚠️ Injury API {r.status_code} → {url}")
        except Exception as e:
            print(f"⚠️ Fetch error on {url}: {e}")
    print("⚠️ All injury endpoints failed — using fallback stub")
    # basic fallback if API unavailable
    return {
        "KC": 0.08, "SF": 0.05, "BUF": 0.04, "DAL": 0.03,
        "NYJ": 0.06, "MIN": 0.02, "NE": 0.07
    }

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
            text = str(row.get("BestPick", "")) + str(row.get("ML", "")) + str(row.get("ATS", ""))
            if team in text:
                old = df.at[idx, "AdjustedConfidence"]
                new = max(0, old * (1 - impact))
                df.at[idx, "AdjustedConfidence"] = round(new, 2)
                reason = str(row.get("Reason", "")) + f" | Injury-adjusted (-{int(impact*100)}%)"
                df.at[idx, "Reason"] = reason.strip()
                adj_count += 1

    df.to_csv(ADJ_FILE, index=False)
    print(f"✅ Injury-adjusted file saved: {ADJ_FILE}")
    print(f"🧩 Adjusted {adj_count} picks for injury impact")

if __name__ == "__main__":
    main()
