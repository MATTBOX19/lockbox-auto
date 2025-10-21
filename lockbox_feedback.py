#!/usr/bin/env python3
"""
lockbox_feedback.py — Phase 11
Tracks completed games, compares LockBox picks vs real results,
and automatically adjusts predictor_config.json to improve win rate.
"""

import os
import json
import pandas as pd
import requests
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ======= PATHS =======
ROOT = Path(".")
OUT_DIR = ROOT / "Output"
CONFIG_FILE = OUT_DIR / "predictor_config.json"
PREDICTIONS_DIR = OUT_DIR
SCORES_API = "https://api.the-odds-api.com/v4/sports/{sport}/scores/"

API_KEY = os.getenv("ODDS_API_KEY")

# ======= LOAD CONFIG =======
CONFIG_DEFAULTS = {
    "ADJUST_FACTOR": 0.35,
    "LOCK_EDGE_THRESHOLD": 0.5,
    "LOCK_CONFIDENCE_THRESHOLD": 51.0,
    "UPSET_EDGE_THRESHOLD": 0.3
}

def load_config():
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE) as f:
                cfg = json.load(f)
                print(f"🧠 Loaded adaptive config: {cfg}")
                return {**CONFIG_DEFAULTS, **cfg}
        except Exception as e:
            print(f"⚠️ Failed to load config: {e}")
    return CONFIG_DEFAULTS

# ======= FETCH SCORES =======
def fetch_scores(sport, days=3):
    url = SCORES_API.format(sport=sport)
    params = {"apiKey": API_KEY, "daysFrom": days}
    try:
        r = requests.get(url, params=params, timeout=10)
        if r.status_code != 200:
            print(f"⚠️ {sport} returned {r.status_code}")
            return []
        return r.json()
    except Exception as e:
        print(f"⚠️ Error fetching scores: {e}")
        return []

# ======= MAIN FEEDBACK =======
def evaluate_predictions():
    cfg = load_config()
    latest_csvs = sorted(PREDICTIONS_DIR.glob("Predictions_*.csv"))
    if not latest_csvs:
        print("❌ No predictions found.")
        return
    latest_file = latest_csvs[-1]
    print(f"📂 Evaluating {latest_file.name}")

    df = pd.read_csv(latest_file)
    if df.empty:
        print("❌ CSV empty.")
        return

    sports = df["Sport"].unique()
    all_scores = {}

    for s in sports:
        key_map = {
            "NFL": "americanfootball_nfl",
            "NCAAF": "americanfootball_ncaaf",
            "NBA": "basketball_nba",
            "NHL": "icehockey_nhl",
            "MLB": "baseball_mlb"
        }
        sport_key = key_map.get(s)
        if not sport_key:
            continue
        scores = fetch_scores(sport_key)
        all_scores[s] = {x["home_team"]: x for x in scores}

    results = []
    wins = 0
    for _, row in df.iterrows():
        sport = row["Sport"]
        teams = [row["Team1"], row["Team2"]]
        pick = row["MoneylinePick"]

        sport_scores = all_scores.get(sport, {})
        matched = None
        for t in teams:
            if t in sport_scores:
                matched = sport_scores[t]
                break
        if not matched or not matched.get("scores"):
            continue

        scores = matched["scores"]
        score_map = {s["name"]: int(s["score"]) for s in scores if s["score"].isdigit()}
        winner = max(score_map, key=score_map.get)
        result = "WIN" if winner == pick else "LOSS"
        if result == "WIN":
            wins += 1

        results.append({
            "Sport": sport,
            "Pick": pick,
            "Winner": winner,
            "Result": result
        })

    if not results:
        print("⚙️ No completed games yet.")
        return

    res_df = pd.DataFrame(results)
    win_rate = (wins / len(results)) * 100
    print(f"📊 Win rate: {win_rate:.1f}% ({wins}/{len(results)})")

    # ======= ADAPTIVE TUNING =======
    adjust = cfg["ADJUST_FACTOR"]
    if win_rate < 60:
        adjust *= 0.9
    elif win_rate > 70:
        adjust *= 1.05
    cfg["ADJUST_FACTOR"] = round(adjust, 3)
    cfg["LAST_WIN_RATE"] = round(win_rate, 2)
    cfg["LAST_UPDATE"] = datetime.now(timezone.utc).isoformat()

    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)
    print(f"✅ Updated {CONFIG_FILE} with new ADJUST_FACTOR={cfg['ADJUST_FACTOR']}")

    res_file = OUT_DIR / f"Results_{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.csv"
    res_df.to_csv(res_file, index=False)
    print(f"📁 Saved results to {res_file}")

if __name__ == "__main__":
    evaluate_predictions()
