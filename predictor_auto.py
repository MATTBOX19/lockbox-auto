#!/usr/bin/env python3
import os, json, uuid, math, time
from pathlib import Path
from datetime import datetime, timezone
import requests
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(".")
OUT_DIR = ROOT / "Output"
OUT_DIR.mkdir(exist_ok=True)
CONFIG_FILE = OUT_DIR / "predictor_config.json"
HISTORY_FILE = OUT_DIR / "history.csv"
LATEST_FILE = OUT_DIR / "Predictions_latest_Explained.csv"

DEFAULTS = {
    "ADJUST_FACTOR": 0.35,
    "LOCK_EDGE_THRESHOLD": 0.5,
    "LOCK_CONFIDENCE_THRESHOLD": 75.0,
    "UPSET_EDGE_THRESHOLD": 0.3,
    "calibrate_lr": 0.05,
    "calibrate_window": 500
}

def load_config():
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r") as f:
                cfg = json.load(f)
            return {**DEFAULTS, **cfg}
        except Exception as e:
            print("⚠️ Config load failed:", e)
    return DEFAULTS.copy()

cfg = load_config()

ADJUST_FACTOR = cfg["ADJUST_FACTOR"]
LOCK_EDGE_THRESHOLD = cfg["LOCK_EDGE_THRESHOLD"]
LOCK_CONFIDENCE_THRESHOLD = cfg["LOCK_CONFIDENCE_THRESHOLD"]
UPSET_EDGE_THRESHOLD = cfg["UPSET_EDGE_THRESHOLD"]

API_KEY = os.getenv("ODDS_API_KEY")
REGION = "us"
MARKETS = "h2h,spreads,totals"
SPORTS = [
    "americanfootball_nfl",
    "americanfootball_ncaaf",
    "basketball_nba",
    "icehockey_nhl",
    "baseball_mlb"
]

ODDS_API_URL = "https://api.the-odds-api.com/v4/sports/{sport}/odds"

def american_to_prob(odds):
    if odds is None: return None
    try:
        o = float(odds)
        return 100.0 / (o + 100.0) if o > 0 else -o / (-o + 100.0)
    except:
        return None

def fetch_odds(sport):
    url = ODDS_API_URL.format(sport=sport)
    params = {"apiKey": API_KEY, "regions": REGION, "markets": MARKETS, "oddsFormat": "american"}
    try:
        r = requests.get(url, params=params, timeout=12)
        if r.status_code != 200:
            print(f"⚠️ API error {r.status_code} for {sport}")
            return []
        data = r.json()
        print(f"📊 Retrieved {len(data)} events for {sport}")
        return data
    except Exception as e:
        print("⚠️ Fetch error:", e)
        return []

def append_history(rows):
    if not rows: return
    keys = ["id","sport","commence_time","team1","team2","pick","pred_prob","edge","ml","ats","ou","reason","created_at","settled","result"]
    df = pd.DataFrame(rows)
    if not HISTORY_FILE.exists():
        df.to_csv(HISTORY_FILE, index=False, columns=keys)
    else:
        df.to_csv(HISTORY_FILE, index=False, header=False, mode="a", columns=keys)
    print(f"✅ Appended {len(df)} rows to history")

rows = []
for sport in SPORTS:
    events = fetch_odds(sport)
    for ev in events:
        try:
            home = ev.get("home_team") or ev.get("home")
            away = ev.get("away_team") or ev.get("away")
            if not home or not away: continue

            bm = ev.get("bookmakers", [{}])[0]
            markets = {m["key"]: m for m in bm.get("markets", [])}

            # --- Moneyline (H2H) ---
            h2h = markets.get("h2h")
            if not h2h: 
                print(f"⚠️ Skipping event (no h2h market) id={ev.get('id')}")
                continue
            outcomes = h2h.get("outcomes", [])
            if len(outcomes) != 2: continue
            team1, team2 = outcomes[0]["name"], outcomes[1]["name"]
            odds1, odds2 = outcomes[0]["price"], outcomes[1]["price"]

            p1 = american_to_prob(odds1)
            p2 = american_to_prob(odds2)
            if not p1 or not p2: continue

            total = p1 + p2
            p1n, p2n = p1 / total, p2 / total
            edge = abs(p1n - p2n) * 100 * ADJUST_FACTOR
            confidence = max(p1n, p2n) * 100
            pick_ml = team1 if p1n > p2n else team2
            ml_pretty = f"{team1}:{odds1} | {team2}:{odds2}"

            # --- ATS (spread) ---
            ats = markets.get("spreads")
            pick_ats, ats_pretty = "", ""
            if ats:
                outcomes = ats.get("outcomes", [])
                if len(outcomes) == 2:
                    s1, s2 = outcomes[0].get("point"), outcomes[1].get("point")
                    if s1 is not None and s2 is not None:
                        implied_margin = (p1n - p2n) * 100 / 2.5
                        team1_cover_diff = implied_margin + s1
                        team2_cover_diff = -implied_margin + s2
                        pick_ats = team1 if abs(team1_cover_diff) < abs(team2_cover_diff) else team2
                        ats_pretty = f"{team1}:{s1} | {team2}:{s2}"

            # --- Over/Under ---
            ou = markets.get("totals")
            pick_ou, ou_pretty = "", ""
            if ou:
                outcomes = ou.get("outcomes", [])
                if len(outcomes) == 2:
                    total_points = outcomes[0].get("point")
                    if total_points:
                        implied_total = (p1n + p2n) * 50
                        pick_ou = "Over" if implied_total > total_points else "Under"
                        ou_pretty = f"Over:{total_points} / Under:{total_points}"

            # --- Emoji Flags ---
            lock_flag = "🔒" if (edge >= LOCK_EDGE_THRESHOLD and confidence >= LOCK_CONFIDENCE_THRESHOLD) else ""
            upset_flag = "💥" if (edge >= UPSET_EDGE_THRESHOLD and confidence < 50) else ""

            row = {
                "Sport": sport.split("_")[-1].upper(),
                "GameTime": ev.get("commence_time", ""),
                "Team1": team1,
                "Team2": team2,
                "MoneylinePick": pick_ml,
                "Confidence": round(confidence, 2),
                "Edge": round(edge, 4),
                "ML": ml_pretty,
                "ATS": ats_pretty,
                "OU": ou_pretty,
                "Reason": "Simulated market differential model",
                "LockEmoji": lock_flag,
                "UpsetEmoji": upset_flag
            }
            rows.append(row)

            event_id = ev.get("id") or str(uuid.uuid4())
            append_history([{
                "id": event_id,
                "sport": sport,
                "commence_time": ev.get("commence_time",""),
                "team1": team1,
                "team2": team2,
                "pick": pick_ml,
                "pred_prob": max(p1n, p2n),
                "edge": edge,
                "ml": ml_pretty,
                "ats": ats_pretty,
                "ou": ou_pretty,
                "reason": "Simulated market differential model",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "settled": False,
                "result": ""
            }])
        except Exception as e:
            print("⚠️ Event error:", e)
            continue

if not rows:
    print("❌ No events processed")
else:
    df = pd.DataFrame(rows)
    # limit locks to top 5 by edge
    df["LockRank"] = df["Edge"].rank(method="first", ascending=False)
    df.loc[df["LockRank"] > 5, "LockEmoji"] = ""
    df.drop(columns=["LockRank"], inplace=True)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    dated_file = OUT_DIR / f"Predictions_{now}_Explained.csv"
    df.to_csv(dated_file, index=False)
    df.to_csv(LATEST_FILE, index=False)
    print(f"✅ Saved {len(df)} rows to {dated_file}")
    print(f"✅ Also updated {LATEST_FILE}")
    print("🚀 Done — ready for web display.")
