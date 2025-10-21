#!/usr/bin/env python3
"""
predictor.py — odds conversion & edge fix

- Converts bookmaker 'price' values correctly (decimal odds or American odds)
- Normalizes market probabilities (vig removal)
- Computes model probability, Edge (percentage points), Confidence (0..100)
- Outputs Output/Predictions_YYYY-MM-DD_Explained.csv with numeric Edge & Confidence
- Lock/Upset logic uses configurable thresholds via constants or env vars
"""

import os
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

# include NCAA football
SPORTS = [
    "americanfootball_nfl",
    "americanfootball_ncaaf",
    "basketball_nba",
    "icehockey_nhl",
    "baseball_mlb",
]
REGION = "us"
MARKETS = "h2h,spreads,totals"
ODDS_API_URL = "https://api.the-odds-api.com/v4/sports/{sport}/odds"
OUT_DIR = Path("Output")
OUT_DIR.mkdir(exist_ok=True)

# MODEL TUNABLES (can be overridden via environment variables)
MODEL_BIAS = float(os.getenv("MODEL_BIAS", "0.0"))          # absolute probability add-on (0.02 = +2%)
ADJUST_FACTOR = float(os.getenv("ADJUST_FACTOR", "0.35"))   # amplifies market deviation from 0.5
LOCK_EDGE_THRESHOLD = float(os.getenv("LOCK_EDGE_THRESHOLD", "1.0"))
LOCK_CONFIDENCE_THRESHOLD = float(os.getenv("LOCK_CONFIDENCE_THRESHOLD", "60.0"))
UPSET_EDGE_THRESHOLD = float(os.getenv("UPSET_EDGE_THRESHOLD", "1.5"))

# ======= HELPERS =======
def odds_price_to_prob(price):
    """
    Convert bookmaker price to implied probability (0..1).
    Handles:
      - Decimal odds (e.g. 1.59) -> prob = 1 / price
      - American odds (e.g. +150, -120) -> classic conversion
      - If value already looks like a probability (0 < price <= 1) return as-is
    Returns None if conversion not possible.
    """
    if price is None:
        return None
    try:
        p = float(price)
    except Exception:
        # try to strip + sign then convert
        s = str(price).strip().replace("+", "")
        try:
            p = float(s)
        except Exception:
            return None

    # Already a probability (0 < p <= 1)
    if 0.0 < p <= 1.0:
        return p

    # American odds (|p| >= 100)
    if abs(p) >= 100.0:
        if p > 0:
            return 100.0 / (p + 100.0)
        else:
            return abs(p) / (abs(p) + 100.0)

    # Decimal odds (>= ~1.01)
    if p >= 1.01:
        try:
            return 1.0 / p
        except Exception:
            return None

    return None

def normalize_market_probs(home_prob, away_prob):
    """Rescale two implied probs to remove vig so they sum to 1 (returns tuple)."""
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
    try:
        return max(lo, min(hi, float(x)))
    except Exception:
        return lo

def calculate_edge(model_prob, market_prob):
    """Return Edge as percentage points (e.g. 2.21)."""
    if model_prob is None or market_prob is None:
        return None
    return round((model_prob - market_prob) * 100.0, 2)

def compute_model_home_prob(market_home_prob):
    """
    Dynamic model placeholder:
      model_p = market_home_prob + (market_home_prob - 0.5) * ADJUST_FACTOR + MODEL_BIAS
    Keeps result clamped to [0.01, 0.99].
    """
    if market_home_prob is None:
        return 0.52
    model_p = market_home_prob + (market_home_prob - 0.5) * ADJUST_FACTOR + MODEL_BIAS
    return clamp(model_p, lo=0.01, hi=0.99)

def safe_extract_ml_spread_total(bookmakers, home_team, away_team):
    """
    Extract ML prices and human-friendly spread/total text from first bookmaker.
    Returns: (ml_home_price, ml_away_price, spread_text, total_text)
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

                # Convert raw price to implied probabilities (0..1)
                raw_home_prob = odds_price_to_prob(ml_home_raw) if ml_home_raw is not None else None
                raw_away_prob = odds_price_to_prob(ml_away_raw) if ml_away_raw is not None else None

                market_home_prob, market_away_prob = normalize_market_probs(raw_home_prob, raw_away_prob)

                model_home_prob = compute_model_home_prob(market_home_prob)
                model_away_prob = 1.0 - model_home_prob

                pick_is_home = model_home_prob >= model_away_prob
                pick_team = home_team if pick_is_home else away_team
                pick_model_prob = model_home_prob if pick_is_home else model_away_prob
                pick_market_prob = market_home_prob if pick_is_home else market_away_prob

                edge = calculate_edge(pick_model_prob, pick_market_prob) if pick_market_prob is not None else None
                confidence = round(pick_model_prob * 100.0, 1) if pick_model_prob is not None else 0.0

                # lock/upset detection (explicit booleans -> emoji strings)
                is_lock = False
                is_upset = False
                try:
                    if edge is not None:
                        if edge >= LOCK_EDGE_THRESHOLD and confidence >= LOCK_CONFIDENCE_THRESHOLD:
                            is_lock = True
                        if (pick_market_prob is not None and pick_market_prob < 0.5) and (edge >= UPSET_EDGE_THRESHOLD):
                            is_upset = True
                except Exception:
                    pass

                ml_display = ""
                try:
                    if ml_home_raw is not None or ml_away_raw is not None:
                        ml_display = f"{home_team}:{ml_home_raw if ml_home_raw is not None else 'N/A'} | {away_team}:{ml_away_raw if ml_away_raw is not None else 'N/A'}"
                except Exception:
                    ml_display = ""

                lock_emoji = "🔒" if is_lock else ""
                upset_emoji = "🚨" if is_upset else ""

                row = {
                    "Sport": sport,
                    "GameTime": commence,
                    "Team1": home_team,
                    "Team2": away_team,
                    "MoneylinePick": pick_team,
                    "Confidence": confidence,                 # numeric 0..100
                    "Edge": edge if edge is not None else 0.0, # numeric percent points
                    "ML": ml_display,
                    "ATS": spread_text if spread_text else "",
                    "OU": total_text if total_text else "",
                    "Reason": "Model vs Market probability differential",
                    "LockEmoji": lock_emoji,
                    "UpsetEmoji": upset_emoji,
                }

                all_rows.append(row)

            except Exception as e:
                print(f"Error parsing game entry: {e}")

    if not all_rows:
        print("⚠️ No predictions generated - output CSV will not be written.")
        return

    df = pd.DataFrame(all_rows)
    # map sport keys to friendly labels for UI
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

    # quick stats for tuning
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
