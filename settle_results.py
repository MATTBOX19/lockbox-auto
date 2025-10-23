#!/usr/bin/env python3
"""
settle_results.py — LockBox automatic results grader (BestPick version)

This version matches your current file format:
Columns: ['Sport', 'GameTime', 'BestPick', 'Confidence', 'Edge', 'ML', 'ATS', 'OU', 'Reason', 'LockEmoji', 'UpsetEmoji']

It fetches final scores via The Odds API, determines whether the picked team won,
and writes a new /Output/Predictions_<date>_Settled.csv
"""

import os, requests, pandas as pd
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(".")
OUT_DIR = ROOT / "Output"
LATEST_FILE = OUT_DIR / "Predictions_latest_Explained.csv"
SETTLED_FILE = OUT_DIR / f"Predictions_{datetime.now(timezone.utc).strftime('%Y-%m-%d')}_Settled.csv"

API_KEY = os.getenv("ODDS_API_KEY")
RESULTS_URL = "https://api.the-odds-api.com/v4/sports/{sport}/scores"

SPORT_MAP = {
    "NFL": "americanfootball_nfl",
    "NCAAF": "americanfootball_ncaaf",
    "NBA": "basketball_nba",
    "NHL": "icehockey_nhl",
    "MLB": "baseball_mlb",
}

def fetch_results(api_sport):
    url = RESULTS_URL.format(sport=api_sport)
    try:
        r = requests.get(url, params={"apiKey": API_KEY, "daysFrom": 3}, timeout=15)
        if r.status_code != 200:
            print(f"⚠️ API error {r.status_code} for {api_sport}")
            return []
        data = r.json()
        print(f"📊 Retrieved {len(data)} results for {api_sport}")
        return data
    except Exception as e:
        print(f"⚠️ Fetch error for {api_sport}: {e}")
        return []

def normalize_team_name(name: str):
    """Try to normalize short/alt names for better matching."""
    name = str(name or "").strip().lower()
    return name.replace("state", "st").replace("saint", "st").replace(".", "").replace("-", " ")

def determine_result(bestpick, sport_results):
    """Decide Win/Loss for BestPick (ML or ATS style)."""
    try:
        if not bestpick:
            return "NoPick"

        # Extract clean team name (strip "(ATS)" or "(ML)" or "(OU)")
        team = bestpick.split("(")[0].strip()
        team_norm = normalize_team_name(team)

        for g in sport_results:
            home = normalize_team_name(g.get("home_team"))
            away = normalize_team_name(g.get("away_team"))
            if team_norm not in [home, away]:
                continue

            scores = g.get("scores", [])
            if not scores or len(scores) != 2:
                continue
            sh = next((float(s["score"]) for s in scores if normalize_team_name(s["name"]) == home), None)
            sa = next((float(s["score"]) for s in scores if normalize_team_name(s["name"]) == away), None)
            if sh is None or sa is None:
                continue

            winner = home if sh > sa else away
            return "Win" if team_norm == winner else "Loss"
        return "NoMatch"
    except Exception as e:
        print(f"⚠️ Result match error: {e}")
        return "Error"

def main():
    if not LATEST_FILE.exists():
        print("❌ No latest predictions file found.")
        return

    df = pd.read_csv(LATEST_FILE)
    df.columns = [c.strip() for c in df.columns]

    df["ML_Result"] = "Pending"
    df["Settled"] = False

    for sport, api_sport in SPORT_MAP.items():
        results = fetch_results(api_sport)
        sport_mask = df["Sport"].astype(str).str.upper() == sport
        for idx in df[sport_mask].index:
            pick = df.loc[idx, "BestPick"]
            res = determine_result(pick, results)
            if res in ["Win", "Loss"]:
                df.at[idx, "ML_Result"] = res
                df.at[idx, "Settled"] = True

    df.to_csv(SETTLED_FILE, index=False)
    print(f"✅ Settled file saved → {SETTLED_FILE}")

if __name__ == "__main__":
    main()
