#!/usr/bin/env python3
"""
predictor.py — Phase 10c (fixed)
Now robustly finds the 'h2h' market across bookmakers and logs skips.
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

# friendly sport mapping
SPORT_MAP = {
    "americanfootball_nfl": "NFL",
    "americanfootball_ncaaf": "CFB",
    "americanfootball_ncaa": "CFB",
    "basketball_nba": "NBA",
    "baseball_mlb": "MLB",
    "icehockey_nhl": "NHL"
}

# ======= FETCH ODDS =======
def fetch_odds(sport):
    url = ODDS_API_URL.format(sport=sport)
    params = {"apiKey": API_KEY, "regions": REGION, "markets": MARKETS, "oddsFormat": "american"}
    try:
        r = requests.get(url, params=params, timeout=12)
        if r.status_code != 200:
            print(f"⚠️ API returned {r.status_code} for {sport}: {r.text[:200]}")
            return []
        data = r.json()
        print(f"📊 Retrieved {len(data)} events for {sport}")
        return data
    except Exception as e:
        print(f"⚠️ Error fetching {sport}: {e}")
        return []

def find_h2h_market(bookmakers):
    """
    Search all bookmakers for a market with key == 'h2h'.
    Return the market dict and the bookmaker key/title used, or (None, None).
    """
    for b in bookmakers or []:
        for m in b.get("markets", []) or []:
            if m.get("key") == "h2h":
                return m, b.get("key") or b.get("title")
    return None, None

# ======= MAIN LOGIC =======
rows = []
skipped = 0
events_processed = 0

for sport in SPORTS:
    events = fetch_odds(sport)
    for ev in events:
        try:
            # Use the API's home/away fields first (v4)
            home = ev.get("home_team") or ev.get("home") or ev.get("homeTeam")
            away = ev.get("away_team") or ev.get("away") or ev.get("awayTeam")
            if not home or not away:
                # Try to pull teams from outcomes later, but skip if missing
                print(f"⚠️ Skipping event (no home/away): id={ev.get('id')}")
                skipped += 1
                continue

            # find an h2h market across available bookmakers
            market, bookmaker_key = find_h2h_market(ev.get("bookmakers", []))
            if not market:
                # log available market keys for debugging
                available = []
                for b in ev.get("bookmakers", []):
                    available.extend([m.get("key") for m in b.get("markets", []) if m.get("key")])
                print(f"⚠️ Skipping event (no h2h market) id={ev.get('id')} available_markets={sorted(set(available))}")
                skipped += 1
                continue

            outcomes = market.get("outcomes") or []
            # moneyline h2h expects two outcomes
            if len(outcomes) != 2:
                print(f"⚠️ Skipping event (h2h outcomes != 2) id={ev.get('id')} outcomes_len={len(outcomes)}")
                skipped += 1
                continue

            # outcome ordering may not follow home/away; we'll use names directly
            team1 = outcomes[0].get("name")
            team2 = outcomes[1].get("name")
            odds1 = outcomes[0].get("price")
            odds2 = outcomes[1].get("price")

            p1 = american_to_prob(odds1)
            p2 = american_to_prob(odds2)
            if p1 is None or p2 is None:
                print(f"⚠️ Skipping event (invalid odds) id={ev.get('id')} odds1={odds1} odds2={odds2}")
                skipped += 1
                continue

            # normalize probabilities to sum to 1
            total = p1 + p2
            if total <= 0:
                print(f"⚠️ Skipping event (bad probs) id={ev.get('id')} p1={p1} p2={p2}")
                skipped += 1
                continue
            p1, p2 = p1 / total, p2 / total

            implied_edge = abs(p1 - p2) * 100 * ADJUST_FACTOR
            confidence = max(p1, p2) * 100
            pick = team1 if p1 > p2 else team2

            sport_friendly = SPORT_MAP.get(sport, sport.split("_")[-1].upper())

            rows.append({
                "Sport": sport_friendly,
                "SportRaw": sport,
                "GameTime": ev.get("commence_time", ""),
                "Team1": team1,
                "Team2": team2,
                "HomeTeam": home,
                "AwayTeam": away,
                "Bookmaker": bookmaker_key or "",
                "MoneylinePick": pick,
                "Confidence(%)": round(confidence, 1),
                "Confidence": round(confidence, 1),
                "Edge": f"{implied_edge:.2f}%",
                "EdgeValue": implied_edge,
                "LockEmoji": "🔒" if (implied_edge > LOCK_EDGE_THRESHOLD and confidence > LOCK_CONFIDENCE_THRESHOLD) else "",
                "UpsetEmoji": "💥" if (implied_edge > UPSET_EDGE_THRESHOLD and confidence < 50) else "",
                "Reason": "Model vs Market probability differential"
            })
            events_processed += 1

        except Exception as e:
            print(f"⚠️ Skipped event due to exception: {e}")
            skipped += 1

# ======= OUTPUT =======
if not rows:
    print("❌ No events processed successfully.")
else:
    df = pd.DataFrame(rows)
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_file = OUT_DIR / f"Predictions_{date_str}_Explained.csv"
    df.to_csv(out_file, index=False)
    unique_sports = sorted(df["Sport"].dropna().unique().tolist())
    print("✅ Unique sports saved in CSV:", unique_sports)
    print(f"✅ Saved predictions to {out_file} (rows={len(df)}, processed={events_processed}, skipped={skipped})")
