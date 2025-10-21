#!/usr/bin/env python3
"""
predictor.py

Updated: dynamic model scaling for visible Edges & Confidence spread.

Changes:
- Adds stronger ADJUST_FACTOR = 4.0 for wider Edge/Confidence separation
- Keeps bias = 0.0 for balance
- Maintains safe rounding, emojis, and CSV export
"""

import os
import math
import requests
import pandas as pd
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ======= CONFIG =======
API_KEY = os.getenv("ODDS_API_KEY")
if not API_KEY:
    print("⚠️ Warning: ODDS_API_KEY not set in environment. API calls will likely fail.")

SPORTS = ["americanfootball_nfl", "americanfootball_ncaaf", "basketball_nba", "icehockey_nhl", "baseball_mlb"]
REGION = "us"
MARKETS = "h2h,spreads,totals"
ODDS_API_URL = "https://api.the-odds-api.com/v4/sports/{sport}/odds"

# ======= MODEL PARAMETERS =======
MODEL_BIAS = 0.0
ADJUST_FACTOR = 4.0           # stronger scaling for visible spread
LOCK_EDGE_THRESHOLD = 1.0
LOCK_CONFIDENCE_THRESHOLD = 60.0
UPSET_EDGE_THRESHOLD = 0.5

OUT_DIR = Path("Output")
OUT_DIR.mkdir(exist_ok=True)


# ======= FUNCTIONS =======
def implied_prob(odds):
    try:
        odds = float(odds)
        return 100 / (odds + 100) if odds > 0 else abs(odds) / (abs(odds) + 100)
    except:
        return None


def calculate_edge(model_prob, market_prob):
    if model_prob is None or market_prob is None:
        return None
    return round((model_prob - market_prob) * 100, 2)


def emoji_for_pick(lock=False, upset=False):
    if lock:
        return "🔒"
    elif upset:
        return "🚨"
    return ""


# ======= MAIN MODEL =======
def run_predictor():
    all_rows = []

    for sport in SPORTS:
        print(f"📊 Fetching {sport} odds...")
        try:
            resp = requests.get(
                ODDS_API_URL.format(sport=sport),
                params={"apiKey": API_KEY, "regions": REGION, "markets": MARKETS}
            )
            data = resp.json()
        except Exception as e:
            print(f"Error fetching {sport} odds: {e}")
            continue

        if not data:
            print(f"No data for {sport}.")
            continue

        for game in data:
            try:
                teams = game.get("home_team"), game.get("away_team")
                commence_time = game.get("commence_time")
                bookmakers = game.get("bookmakers", [])
                if not bookmakers:
                    continue

                book = bookmakers[0]
                markets = {m["key"]: m for m in book.get("markets", [])}
                h2h = markets.get("h2h", {}).get("outcomes", [])
                spreads = markets.get("spreads", {}).get("outcomes", [])
                totals = markets.get("totals", {}).get("outcomes", [])

                if len(h2h) != 2:
                    continue

                home_team = h2h[0]["name"]
                away_team = h2h[1]["name"]
                home_price = h2h[0]["price"]
                away_price = h2h[1]["price"]

                home_prob = implied_prob(home_price)
                away_prob = implied_prob(away_price)
                market_home_prob = home_prob / (home_prob + away_prob) if home_prob and away_prob else None

                if market_home_prob is None:
                    continue

                # Model logic: amplify difference from 0.5
                model_p = market_home_prob + (market_home_prob - 0.5) * ADJUST_FACTOR + MODEL_BIAS
                model_p = max(0, min(1, model_p))

                edge = calculate_edge(model_p, market_home_prob)
                confidence = round(model_p * 100, 1)

                # Determine lock/upset
                lock = edge >= LOCK_EDGE_THRESHOLD and confidence >= LOCK_CONFIDENCE_THRESHOLD
                upset = (market_home_prob < 0.5) and (edge >= UPSET_EDGE_THRESHOLD)
                lock_emoji = emoji_for_pick(lock=lock)
                upset_emoji = emoji_for_pick(upset=upset)

                row = {
                    "Sport": sport,
                    "GameTime": commence_time,
                    "Team1": home_team,
                    "Team2": away_team,
                    "MoneylinePick": home_team if model_p >= 0.5 else away_team,
                    "Confidence": confidence,
                    "Edge": edge,
                    "ML": f"{home_team}:{home_price} | {away_team}:{away_price}",
                    "ATS": " | ".join([f"{x['name']}:{x.get('point', '')}" for x in spreads]) if spreads else "",
                    "OU": " / ".join([f"{x['name']}:{x.get('point', '')}" for x in totals]) if totals else "",
                    "Reason": "Model vs Market probability differential",
                    "LockEmoji": lock_emoji,
                    "UpsetEmoji": upset_emoji,
                }

                all_rows.append(row)

            except Exception as e:
                print(f"Error parsing game entry: {e}")

    if not all_rows:
        print("⚠️ No predictions generated.")
        return

    df = pd.DataFrame(all_rows)
    df["Sport"] = df["Sport"].replace({
        "americanfootball_nfl": "NFL",
        "americanfootball_ncaaf": "CFB",
        "basketball_nba": "NBA",
        "baseball_mlb": "MLB",
        "icehockey_nhl": "NHL"
    })

    out_file = OUT_DIR / f"Predictions_{datetime.now().strftime('%Y-%m-%d')}_Explained.csv"
    df.to_csv(out_file, index=False)
    print(f"✅ Saved predictions to {out_file} (rows={len(df)})")

    try:
        edges = df["Edge"].astype(float)
        confs = df["Confidence"].astype(float)
        print("Edge summary (min / mean / max):", round(edges.min(), 2), "/", round(edges.mean(), 2), "/", round(edges.max(), 2))
        print("Confidence summary (min / mean / max):", round(confs.min(), 2), "/", round(confs.mean(), 2), "/", round(confs.max(), 2))
        locks_count = df["LockEmoji"].astype(str).map(lambda s: 1 if s.strip() else 0).sum()
        upsets_count = df["UpsetEmoji"].astype(str).map(lambda s: 1 if s.strip() else 0).sum()
        print(f"Locks: {locks_count} | Upsets: {upsets_count}")
    except Exception as e:
        print(f"Note: unable to compute summary stats: {e}")


if __name__ == "__main__":
    run_predictor()
