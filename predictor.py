#!/usr/bin/env python3
"""
predictor.py

Phase 10: Adaptive Config Integration

Now dynamically loads tunable parameters from /Output/predictor_config.json,
automatically updated by lockbox_feedback.py.
"""

import os
import math
import json
import requests
import pandas as pd
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ======= PATHS & CONFIG =======
ROOT = Path(".")
OUT_DIR = ROOT / "Output"
OUT_DIR.mkdir(exist_ok=True)
CONFIG_FILE = OUT_DIR / "predictor_config.json"

# Default parameters (fallback)
CONFIG_DEFAULTS = {
    "ADJUST_FACTOR": 0.35,
    "LOCK_EDGE_THRESHOLD": 0.5,
    "LOCK_CONFIDENCE_THRESHOLD": 51.0,
    "UPSET_EDGE_THRESHOLD": 0.3
}

def load_config():
    """Load adaptive parameters from JSON (created by lockbox_feedback.py)."""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE) as f:
                cfg = json.load(f)
                print(f"🧠 Loaded adaptive config: {cfg}")
                return {**CONFIG_DEFAULTS, **cfg}
        except Exception as e:
            print(f"⚠️ Failed to load config: {e}")
    print("⚙️ Using default parameters.")
    return CONFIG_DEFAULTS

# Load parameters
params = load_config()
ADJUST_FACTOR = params["ADJUST_FACTOR"]
LOCK_EDGE_THRESHOLD = params["LOCK_EDGE_THRESHOLD"]
LOCK_CONFIDENCE_THRESHOLD = params["LOCK_CONFIDENCE_THRESHOLD"]
UPSET_EDGE_THRESHOLD = params["UPSET_EDGE_THRESHOLD"]

# ======= MODEL INPUT CONFIG =======
API_KEY = os.getenv("ODDS_API_KEY")
REGION = "us"
MARKETS = "h2h,spreads,totals"
ODDS_API_URL = "https://api.the-odds-api.com/v4/sports/{sport}/odds"
SPORTS = ["americanfootball_nfl", "americanfootball_ncaaf", "basketball_nba", "icehockey_nhl", "baseball_mlb"]

# ======= MODEL LOGIC =======
def american_to_prob(odds):
    if odds > 0:
        return 100 / (odds + 100)
    return -odds / (-odds + 100)

def fetch_odds(sport):
    url = ODDS_API_URL.format(sport=sport)
    try:
        r = requests.get(url, params={"apiKey": API_KEY, "regions": REGION, "markets": MARKETS})
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"⚠️ Error fetching odds for {sport}: {e}")
        return []

def calculate_model_probs(market_home_prob):
    """Adjust the base market probability using ADJUST_FACTOR."""
    return market_home_prob + (market_home_prob - 0.5) * ADJUST_FACTOR

def process_sport(sport):
    data = fetch_odds(sport)
    rows = []
    for game in data:
        teams = game.get("teams", [])
        if len(teams) < 2:
            continue
        team1, team2 = teams[0], teams[1]

        markets = {m["key"]: m for m in game.get("bookmakers", [{}])[0].get("markets", [])}
        h2h = markets.get("h2h", {}).get("outcomes", [])

        if not h2h or len(h2h) < 2:
            continue

        home_team = game.get("home_team")
        away_team = [t for t in teams if t != home_team][0]

        try:
            odds_home = next(o["price"] for o in h2h if o["name"] == home_team)
            odds_away = next(o["price"] for o in h2h if o["name"] == away_team)
        except StopIteration:
            continue

        prob_home = american_to_prob(odds_home)
        prob_away = american_to_prob(odds_away)
        prob_sum = prob_home + prob_away
        prob_home /= prob_sum
        prob_away /= prob_sum

        model_home = calculate_model_probs(prob_home)
        model_away = 1 - model_home
        edge = abs(model_home - prob_home)
        pick = home_team if model_home > 0.5 else away_team
        confidence = max(model_home, model_away) * 100

        lock = "🔒" if (edge >= LOCK_EDGE_THRESHOLD and confidence >= LOCK_CONFIDENCE_THRESHOLD) else ""
        upset = "🚨" if (pick == away_team and edge >= UPSET_EDGE_THRESHOLD) else ""

        rows.append({
            "Sport": sport.replace("americanfootball_", "").upper(),
            "GameTime": game.get("commence_time"),
            "Team1": home_team,
            "Team2": away_team,
            "MoneylinePick": pick,
            "Confidence": round(confidence, 2),
            "Edge": round(edge, 2),
            "ML": f"{home_team}:{odds_home} | {away_team}:{odds_away}",
            "Reason": "Model vs Market probability differential",
            "LockEmoji": lock,
            "UpsetEmoji": upset
        })
    return rows

def main():
    all_rows = []
    for sport in SPORTS:
        rows = process_sport(sport)
        all_rows.extend(rows)

    if not all_rows:
        print("No odds data returned.")
        return

    df = pd.DataFrame(all_rows)
    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    out_file = OUT_DIR / f"Predictions_{date_str}_Explained.csv"
    df.to_csv(out_file, index=False)
    print(f"✅ Saved predictions to {out_file} (rows={len(df)})")

    lock_count = df["LockEmoji"].astype(bool).sum()
    upset_count = df["UpsetEmoji"].astype(bool).sum()
    print(f"Locks: {lock_count} | Upsets: {upset_count}")

if __name__ == "__main__":
    main()
