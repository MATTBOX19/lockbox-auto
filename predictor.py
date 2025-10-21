#!/usr/bin/env python3
"""
predictor.py — Phase 10c
Now correctly parses The Odds API v4 structure.
"""

import os
import math
import json
import requests
import pandas as pd
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ======= PATHS & CONFIG =======
ROOT = Path(".")
OUT_DIR = ROOT / "Output"
OUT_DIR.mkdir(exist_ok=True)
CONFIG_FILE = OUT_DIR / "predictor_config.json"

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
    print("⚙️ Using default parameters.")
    return CONFIG_DEFAULTS

params = load_config()
ADJUST_FACTOR = params["ADJUST_FACTOR"]
LOCK_EDGE_THRESHOLD = params["LOCK_EDGE_THRESHOLD"]
LOCK_CONFIDENCE_THRESHOLD = params["LOCK_CONFIDENCE_THRESHOLD"]
UPSET_EDGE_THRESHOLD = params["UPSET_EDGE_THRESHOLD"]

# ======= API CONFIG =======
API_KEY = os.getenv("ODDS_API_KEY")
REGION = "us"
MARKETS = "h2h,spreads,totals"
ODDS_API_URL = "https://api.the-odds-api.com/v4/sports/{sport}/odds"
SPORTS = ["americanfootball_nfl", "americanfootball_ncaaf", "basketball_nba", "icehockey_nhl", "baseball_mlb"]

# ======= UTILS =======
def american_to_prob(odds):
    if odds is None:
        return None
    try:
        odds = float(odds)
        if odds > 0:
            return 100 / (odds + 100)
        return -odds / (-odds + 100)
    except:
        return None

# ======= FETCH ODDS =======
def fetch_odds(sport):
    url = ODDS_API_URL.format(sport=sport)
    params = {"apiKey": API_KEY, "regions": REGION, "markets": MARKETS, "oddsFormat": "american"}
    try:
        r = requests.get(url, params=params, timeout=10)
        if r.status_code != 200:
            print(f"⚠️ API returned {r.status_code} for {sport}: {r.text[:200]}")
            return []
        data = r.json()
        print(f"📊 Retrieved {len(data)} events for {sport}")
        return data
    except Exception as e:
        print(f"⚠️ Error fetching {sport}: {e}")
        return []

# ======= MAIN LOGIC =======
rows = []
for sport in SPORTS:
    events = fetch_odds(sport)
    for ev in events:
        try:
            home = ev.get("home_team")
            away = ev.get("away_team")
            if not home or not away:
                continue

            bookmaker = ev["bookmakers"][0]
            market = bookmaker["markets"][0]
            outcomes = market["outcomes"]

            if len(outcomes) != 2:
                continue

            team1, team2 = outcomes[0]["name"], outcomes[1]["name"]
            odds1, odds2 = outcomes[0]["price"], outcomes[1]["price"]

            p1 = american_to_prob(odds1)
            p2 = american_to_prob(odds2)
            if not p1 or not p2:
                continue

            total = p1 + p2
            p1, p2 = p1 / total, p2 / total
            implied_edge = abs(p1 - p2) * 100 * ADJUST_FACTOR
            confidence = max(p1, p2) * 100
            pick = team1 if p1 > p2 else team2

            rows.append({
                "Sport": sport.split("_")[-1].upper(),
                "GameTime": ev.get("commence_time", ""),
                "HomeTeam": home,
                "AwayTeam": away,
                "MoneylinePick": pick,
                "Confidence(%)": round(confidence, 1),
                "Edge": f"{implied_edge:.2f}%",
                "LockEmoji": "🔒" if implied_edge > LOCK_EDGE_THRESHOLD and confidence > LOCK_CONFIDENCE_THRESHOLD else "",
                "UpsetEmoji": "💥" if implied_edge > UPSET_EDGE_THRESHOLD and confidence < 50 else "",
                "Reason": "Model vs Market probability differential"
            })
        except Exception as e:
            print(f"⚠️ Skipped event: {e}")

# ======= OUTPUT =======
if not rows:
    print("❌ No events processed successfully.")
else:
    df = pd.DataFrame(rows)
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_file = OUT_DIR / f"Predictions_{date_str}_Explained.csv"
    df.to_csv(out_file, index=False)
    print(f"✅ Saved predictions to {out_file} (rows={len(df)})")
