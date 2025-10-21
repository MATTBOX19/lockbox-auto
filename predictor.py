#!/usr/bin/env python3
"""
predictor.py — Phase 10c (debug-friendly, writes Predictions_latest_Explained.csv)
"""

import os
import json
import requests
import pandas as pd
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

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

API_KEY = os.getenv("ODDS_API_KEY")
REGION = "us"
MARKETS = "h2h,spreads,totals"
ODDS_API_URL = "https://api.the-odds-api.com/v4/sports/{sport}/odds"
SPORTS = ["americanfootball_nfl", "americanfootball_ncaaf", "basketball_nba", "icehockey_nhl", "baseball_mlb"]

def odds_to_prob(price):
    """Convert API price (may be decimal odds or American) to implied probability (0..1).
       Heuristic: negative values -> American; positive values:
         - if <=1: invalid
         - if between 1.01 and 10 -> treat as decimal (1/odds)
         - otherwise treat as American (+150 etc) unless negative
    """
    if price is None:
        return None
    try:
        o = float(price)
    except Exception:
        return None

    # American: negative numbers are american; very large absolute values probably american too
    if o <= 0 or abs(o) >= 10:
        # american
        try:
            if o > 0:
                return 100.0 / (o + 100.0)
            else:
                return -o / (-o + 100.0)
        except Exception:
            return None
    else:
        # decimal odds (typical: 1.01 .. 10)
        if o <= 1.01:
            return None
        return 1.0 / o

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

# mapper to friendly sport code
SPORT_MAP = {
    "americanfootball_nfl": "NFL",
    "americanfootball_ncaaf": "CFB",
    "basketball_nba": "NBA",
    "baseball_mlb": "MLB",
    "icehockey_nhl": "NHL"
}

rows = []
processed = 0
skipped = 0
for sport in SPORTS:
    events = fetch_odds(sport)
    for ev in events:
        processed += 1
        ev_id = ev.get("id", "<no-id>")
        try:
            # try to find available markets per bookmaker
            bks = ev.get("bookmakers", []) or []
            if not bks:
                print(f"⚠️ Skipping event (no bookmakers) id={ev_id}")
                skipped += 1
                continue

            # pick first bookmaker that has markets (prefer draftkings if present)
            bookmaker = None
            for b in bks:
                if b.get("markets"):
                    bookmaker = b
                    if b.get("key") == "draftkings":
                        break
            if not bookmaker:
                print(f"⚠️ Skipping event (no markets) id={ev_id}")
                skipped += 1
                continue

            available_markets = [m.get("key") for m in bookmaker.get("markets", [])]
            # prefer h2h market
            h2h_market = None
            spreads_market = None
            totals_market = None
            for m in bookmaker.get("markets", []):
                if m.get("key") == "h2h":
                    h2h_market = m
                if m.get("key") == "spreads":
                    spreads_market = m
                if m.get("key") == "totals":
                    totals_market = m

            if not h2h_market:
                print(f"⚠️ Skipping event (no h2h market) id={ev_id} available_markets={available_markets}")
                skipped += 1
                continue

            outcomes = h2h_market.get("outcomes", []) or []
            if len(outcomes) != 2:
                print(f"⚠️ Skipping event (unexpected h2h outcomes) id={ev_id} len_outcomes={len(outcomes)}")
                skipped += 1
                continue

            team1_name = outcomes[0].get("name")
            team2_name = outcomes[1].get("name")
            price1 = outcomes[0].get("price")
            price2 = outcomes[1].get("price")

            p1 = odds_to_prob(price1)
            p2 = odds_to_prob(price2)
            if p1 is None or p2 is None:
                print(f"⚠️ Skipping event (bad prices) id={ev_id} prices=({price1},{price2})")
                skipped += 1
                continue

            # normalize probs
            total = p1 + p2
            if total <= 0:
                print(f"⚠️ Skipping event (invalid total probs) id={ev_id} total={total}")
                skipped += 1
                continue
            p1n, p2n = p1 / total, p2 / total

            implied_edge = abs(p1n - p2n) * 100.0 * ADJUST_FACTOR  # numeric small float (matches previous flow)
            confidence = max(p1n, p2n) * 100.0
            pick = team1_name if p1n > p2n else team2_name

            # build ML/ATS/OU strings if possible
            ml_str = f"{team1_name}:{price1} | {team2_name}:{price2}"
            ats_str = ""
            ou_str = ""
            if spreads_market:
                try:
                    s_out = spreads_market.get("outcomes", [])
                    # join spread lines
                    ats_parts = []
                    for o in s_out:
                        n = o.get("name"); sp = o.get("point"); ats_parts.append(f"{n}:{sp:+}")
                    ats_str = " | ".join(ats_parts)
                except Exception:
                    pass
            if totals_market:
                try:
                    t_out = totals_market.get("outcomes", [])
                    # typical totals markets include labels like Over/Under
                    tot_parts = []
                    for o in t_out:
                        if "name" in o and "point" in o:
                            tot_parts.append(f"{o.get('name')}: {o.get('point')}")
                    ou_str = " / ".join(tot_parts) if tot_parts else ""
                except Exception:
                    pass

            # friendly sport label
            sport_label = SPORT_MAP.get(sport, sport.split("_")[-1].upper())

            rows.append({
                "Sport": sport_label,
                "GameTime": ev.get("commence_time", ""),
                "Team1": team1_name,
                "Team2": team2_name,
                "MoneylinePick": pick,
                "Confidence": round(confidence, 2),
                "Edge": round(implied_edge, 4),
                "ML": ml_str,
                "ATS": ats_str,
                "OU": ou_str,
                "Reason": "Model vs Market probability differential",
                "LockEmoji": "🔒" if (implied_edge >= LOCK_EDGE_THRESHOLD and confidence >= LOCK_CONFIDENCE_THRESHOLD) else "",
                "UpsetEmoji": "💥" if (implied_edge >= UPSET_EDGE_THRESHOLD and confidence < 50.0) else ""
            })

        except Exception as e:
            print(f"⚠️ Skipped event (exception) id={ev_id}: {e}")
            skipped += 1

# Output
if not rows:
    print("❌ No events processed successfully.")
else:
    df = pd.DataFrame(rows)
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_file = OUT_DIR / f"Predictions_{date_str}_Explained.csv"
    latest_file = OUT_DIR / "Predictions_latest_Explained.csv"
    df.to_csv(out_file, index=False)
    df.to_csv(latest_file, index=False)
    unique_sports = sorted(df["Sport"].dropna().unique().tolist())
    print(f"✅ Unique sports saved in CSV: {unique_sports}")
    print(f"✅ Saved predictions to {out_file} and {latest_file} (rows={len(df)}, processed={processed}, skipped={skipped})")
