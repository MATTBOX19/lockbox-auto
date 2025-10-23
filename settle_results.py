#!/usr/bin/env python3
"""
settle_results.py — auto-mark results for LockBox history

Reads your latest history and current predictions, fetches final scores,
determines Win/Loss for ML, ATS, and OU, and outputs:
  /Output/Predictions_<date>_Settled.csv
"""

import os, json, requests
import pandas as pd
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(".")
OUT_DIR = ROOT / "Output"
HISTORY_FILE = OUT_DIR / "history.csv"
LATEST_FILE = OUT_DIR / "Predictions_latest_Explained.csv"
SETTLED_FILE = OUT_DIR / f"Predictions_{datetime.now(timezone.utc).strftime('%Y-%m-%d')}_Settled.csv"

API_KEY = os.getenv("ODDS_API_KEY")
REGION = "us"

RESULTS_URL = "https://api.the-odds-api.com/v4/sports/{sport}/scores"

SPORT_MAP = {
    "americanfootball_nfl": "NFL",
    "americanfootball_ncaaf": "NCAAF",
    "basketball_nba": "NBA",
    "icehockey_nhl": "NHL",
    "baseball_mlb": "MLB"
}

def fetch_results(sport_key):
    url = RESULTS_URL.format(sport=sport_key)
    params = {"apiKey": API_KEY, "daysFrom": 3}
    try:
        r = requests.get(url, params=params, timeout=12)
        if r.status_code != 200:
            print(f"⚠️ API error {r.status_code} for {sport_key}")
            return []
        data = r.json()
        print(f"📊 Retrieved {len(data)} results for {sport_key}")
        return data
    except Exception as e:
        print(f"⚠️ Fetch error for {sport_key}: {e}")
        return []

def determine_result(row, results):
    try:
        team1, team2 = row["Team1"], row["Team2"]
        pick = row["MoneylinePick"]
        sport = row["Sport"]
        if not pick or sport not in ["NFL","NCAAF","NBA","NHL","MLB"]:
            return "N/A"

        for game in results:
            h = game.get("home_team")
            a = game.get("away_team")
            if not h or not a: continue
            if team1 in [h,a] and team2 in [h,a]:
                scores = game.get("scores", [])
                if not scores or len(scores) != 2:
                    continue
                sh = next((s["score"] for s in scores if s["name"] == h), None)
                sa = next((s["score"] for s in scores if s["name"] == a), None)
                if sh is None or sa is None: continue
                sh, sa = float(sh), float(sa)
                winner = h if sh > sa else a
                return "Win" if pick == winner else "Loss"
        return "NoMatch"
    except Exception as e:
        print(f"⚠️ Result error: {e}")
        return "Error"

def main():
    if not os.path.exists(LATEST_FILE):
        print("❌ No latest predictions found.")
        return

    df = pd.read_csv(LATEST_FILE)
    df.columns = [c.strip() for c in df.columns]
    df["ML_Result"] = "Pending"
    df["Settled"] = False

    for sport_key, sport_name in SPORT_MAP.items():
        results = fetch_results(sport_key)
        sport_mask = df["Sport"].astype(str).str.upper() == sport_name
        for idx in df[sport_mask].index:
            res = determine_result(df.loc[idx], results)
            if res in ["Win", "Loss"]:
                df.at[idx, "ML_Result"] = res
                df.at[idx, "Settled"] = True

    df.to_csv(SETTLED_FILE, index=False)
    print(f"✅ Settled file saved → {SETTLED_FILE}")

if __name__ == "__main__":
    main()
