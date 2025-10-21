#!/usr/bin/env python3
"""
predictor.py

Produces: Output/Predictions_YYYY-MM-DD_Explained.csv

Purpose:
- Fetch odds from The Odds API (ODDS_API_KEY from env)
- Compute market implied probabilities (vig removed)
- Compute a placeholder model probability (tunable)
- Compute Edge = (model_prob - market_prob) * 100 (numeric)
- Compute Confidence (numeric 0-100 for the chosen pick)
- Add LockEmoji / UpsetEmoji using configurable thresholds
- Output a CSV with a stable schema for the web UI

NOTE: Replace compute_model_home_prob with your production model when ready.
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

SPORTS = ["americanfootball_nfl", "basketball_nba", "icehockey_nhl", "baseball_mlb"]
REGION = "us"
MARKETS = "h2h,spreads,totals"
ODDS_API_URL = "https://api.the-odds-api.com/v4/sports/{sport}/odds"

# MODEL TUNABLES (adjust these to tune Edge/Lock behavior)
MODEL_BIAS = 0.02              # add this much absolute probability to model vs market (0.02 = 2%)
ADJUST_FACTOR = 0.05           # scale factor for how much model exaggerates market distance from 0.5
LOCK_EDGE_THRESHOLD = 4.0      # Edge (percent) required to consider a "Lock"
LOCK_CONFIDENCE_THRESHOLD = 60.0  # Confidence (%) required to consider a "Lock"
UPSET_EDGE_THRESHOLD = 2.0     # Edge (percent) required to consider an "Upset" if pick is market underdog

# Output directory
OUT_DIR = Path("Output")
OUT_DIR.mkdir(exist_ok=True)

# ======= HELPERS =======
def american_odds_to_prob(odds):
    """
    Convert American moneyline odds (e.g. -150, +130) to implied probability (0..1).
    Returns None on failure.
    """
    try:
        odds = float(odds)
    except Exception:
        return None

    if odds > 0:
        return 100.0 / (odds + 100.0)
    else:
        return abs(odds) / (abs(odds) + 100.0)

def normalize_market_probs(home_prob, away_prob):
    """
    Remove bookmaker vig by scaling the raw implied probs to sum to 1.
    If one side missing, return the raw prob and 1 - prob as fallback.
    """
    if home_prob is None and away_prob is None:
        return None, None
    if home_prob is None:
        return None, 1.0
    if away_prob is None:
        return 1.0, None

    total = home_prob + away_prob
    if total <= 0:
        return None, None
    return home_prob / total, away_prob / total

def clamp(x, lo=0.001, hi=0.999):
    return max(lo, min(hi, x))

def calculate_edge(model_prob, market_prob):
    """
    Edge returned as percent float (e.g. 3.25 => 3.25%).
    """
    if model_prob is None or market_prob is None:
        return None
    return round((model_prob - market_prob) * 100.0, 2)

def compute_model_home_prob(market_home_prob):
    """
    Placeholder model logic. This intentionally:
      - starts from market_home_prob (vig-removed)
      - applies a small bias and a small exaggeration based on distance from 0.5
    Replace this function with your production model when ready.
    """
    if market_home_prob is None:
        # fallback neutral
        return 0.52

    adj = ADJUST_FACTOR * (market_home_prob - 0.5)
    model_p = market_home_prob + MODEL_BIAS + adj
    return clamp(model_p, lo=0.01, hi=0.99)

def safe_extract_ml_spread_total(bookmakers, home_team, away_team):
    """
    Extract the most-likely ML for home/away and simple spread/total text for display.
    Returns (ml_home, ml_away, spread_text, total_text)
    """
    ml_home = ml_away = None
    spread_text = ""
    total_text = ""
    try:
        if not bookmakers:
            return ml_home, ml_away, spread_text, total_text
        b0 = bookmakers[0]
        markets = b0.get("markets", [])
        for m in markets:
            key = m.get("key")
            outcomes = m.get("outcomes", [])
            if key == "h2h":
                for o in outcomes:
                    name = o.get("name")
                    price = o.get("price")
                    if name == home_team:
                        ml_home = price
                    elif name == away_team:
                        ml_away = price
                # continue searching spreads/totals too
            elif key == "spreads":
                parts = []
                for o in outcomes:
                    name = o.get("name")
                    point = o.get("point")
                    if name and point is not None:
                        parts.append(f"{name}:{point:+}")
                spread_text = " | ".join(parts)
            elif key == "totals":
                parts = []
                for o in outcomes:
                    label = o.get("name")
                    point = o.get("point")
                    if label and point is not None:
                        parts.append(f"{label}:{point}")
                total_text = " / ".join(parts)
    except Exception:
        pass
    return ml_home, ml_away, spread_text, total_text

# ======= PREDICTOR =======
def run_predictor():
    all_rows = []

    for sport in SPORTS:
        url = ODDS_API_URL.format(sport=sport)
        try:
            r = requests.get(url, params={"apiKey": API_KEY, "regions": REGION, "markets": MARKETS}, timeout=15)
        except Exception as e:
            print(f"⚠️ Network/requests error for {sport}: {e}")
            continue

        if r.status_code != 200:
            print(f"⚠️ Error fetching {sport}: {r.status_code} - {r.text[:200]}")
            continue

        try:
            games = r.json()
        except Exception as e:
            print(f"⚠️ Failed to parse JSON for {sport}: {e}")
            continue

        for g in games:
            try:
                home_team = g.get("home_team")
                away_team = g.get("away_team")
                commence = g.get("commence_time")
                bookmakers = g.get("bookmakers", [])

                ml_home_raw, ml_away_raw, spread_text, total_text = safe_extract_ml_spread_total(bookmakers, home_team, away_team)

                raw_home_prob = american_odds_to_prob(ml_home_raw) if ml_home_raw is not None else None
                raw_away_prob = american_odds_to_prob(ml_away_raw) if ml_away_raw is not None else None

                market_home_prob, market_away_prob = normalize_market_probs(raw_home_prob, raw_away_prob)

                model_home_prob = compute_model_home_prob(market_home_prob)
                model_away_prob = 1.0 - model_home_prob

                pick_is_home = model_home_prob >= model_away_prob
                pick_team = home_team if pick_is_home else away_team
                pick_model_prob = model_home_prob if pick_is_home else model_away_prob
                pick_market_prob = market_home_prob if pick_is_home else market_away_prob

                edge = calculate_edge(pick_model_prob, pick_market_prob) if pick_market_prob is not None else None
                confidence = round(pick_model_prob * 100.0, 1) if pick_model_prob is not None else 0.0

                is_lock = False
                is_upset = False
                try:
                    if edge is not None and confidence is not None:
                        if edge >= LOCK_EDGE_THRESHOLD and confidence >= LOCK_CONFIDENCE_THRESHOLD:
                            is_lock = True
                        if (pick_market_prob is not None and pick_market_prob < 0.5) and (edge is not None and edge >= UPSET_EDGE_THRESHOLD):
                            is_upset = True
                except Exception:
                    pass

                ml_display = ""
                try:
                    if ml_home_raw is not None or ml_away_raw is not None:
                        ml_display = f"{home_team}:{ml_home_raw if ml_home_raw is not None else 'N/A'} | {away_team}:{ml_away_raw if ml_away_raw is not None else 'N/A'}"
                except Exception:
                    ml_display = ""

                row = {
                    "Sport": sport,
                    "GameTime": commence,
                    "Team1": home_team,
                    "Team2": away_team,
                    "MoneylinePick": pick_team,
                    "Confidence": confidence,    # numeric 0..100
                    "Edge": edge if edge is not None else 0.0,  # numeric percent
                    "ML": ml_display,
                    "ATS": spread_text if spread_text else "",
                    "OU": total_text if total_text else "",
                    "Reason": "Model vs Market probability differential",
                    "LockEmoji": "🔒" if is_lock else "",
                    "UpsetEmoji": "🚨" if is_upset else "",
                }

                all_rows.append(row)

            except Exception as e:
                print(f"Error parsing game entry: {e}")

    if not all_rows:
        print("⚠️ No predictions generated - output CSV will not be written.")
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

if __name__ == "__main__":
    run_predictor()
