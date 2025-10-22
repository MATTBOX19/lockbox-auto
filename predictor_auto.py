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

# Always point to the “latest” file for the web
LATEST_FILE = OUT_DIR / "Predictions_latest_Explained.csv"

# Defaults (persisted)
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
            merged = {**DEFAULTS, **cfg}
            print("🧠 Loaded config:", merged)
            return merged
        except Exception as e:
            print("⚠️ Failed to load config:", e)
    print("⚙️ Using defaults")
    return DEFAULTS.copy()

def save_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)
    print("✅ Saved config")

cfg = load_config()
ADJUST_FACTOR = cfg["ADJUST_FACTOR"]
LOCK_EDGE_THRESHOLD = cfg["LOCK_EDGE_THRESHOLD"]
LOCK_CONFIDENCE_THRESHOLD = cfg["LOCK_CONFIDENCE_THRESHOLD"]
UPSET_EDGE_THRESHOLD = cfg["UPSET_EDGE_THRESHOLD"]

# API config
API_KEY = os.getenv("ODDS_API_KEY")
REGION = "us"
MARKETS = "h2h,spreads,totals"
ODDS_API_URL = "https://api.the-odds-api.com/v4/sports/{sport}/odds"
SPORTS = [
    "americanfootball_nfl",
    "americanfootball_ncaaf",
    "basketball_nba",
    "icehockey_nhl",
    "baseball_mlb"
]

def american_to_prob(odds):
    if odds is None:
        return None
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
            print(f"⚠️ API {r.status_code} for {sport}: {r.text[:200]}")
            return []
        data = r.json()
        print(f"📊 Retrieved {len(data)} events for {sport}")
        return data
    except Exception as e:
        print("⚠️ Fetch error", e)
        return []

def append_history(rows):
    keys = ["id","sport","commence_time","team1","team2","pick","pred_prob","edge","ml","ats","ou","reason","created_at","settled","result"]
    if not rows:
        return
    df = pd.DataFrame(rows)
    if not HISTORY_FILE.exists():
        df.to_csv(HISTORY_FILE, index=False, columns=keys)
        print(f"✅ Created history with {len(df)} rows")
    else:
        df.to_csv(HISTORY_FILE, index=False, header=False, mode="a", columns=keys)
        print(f"✅ Appended {len(df)} rows to history")

# ---------- MAIN PREDICTION LOOP ----------
rows = []
processed = 0
skipped = 0

for sport in SPORTS:
    events = fetch_odds(sport)
    for ev in events:
        try:
            home = ev.get("home_team") or ev.get("home")
            away = ev.get("away_team") or ev.get("away")
            bms = ev.get("bookmakers", [])
            if not bms:
                skipped += 1
                continue
            bm = bms[0]
            market = next((m for m in bm.get("markets", []) if m.get("key") == "h2h"), None)
            if not market:
                print(f"⚠️ Skipping event (no h2h market) id={ev.get('id')}")
                skipped += 1
                continue
            outcomes = market.get("outcomes", [])
            if len(outcomes) != 2:
                skipped += 1
                continue
            team1, team2 = outcomes[0]["name"], outcomes[1]["name"]
            odds1, odds2 = outcomes[0]["price"], outcomes[1]["price"]
            p1 = american_to_prob(odds1)
            p2 = american_to_prob(odds2)
            if p1 is None or p2 is None:
                skipped += 1
                continue

            total = p1 + p2
            p1n, p2n = p1 / total, p2 / total
            implied_edge = abs(p1n - p2n) * 100 * cfg.get("ADJUST_FACTOR", ADJUST_FACTOR)
            confidence = max(p1n, p2n) * 100
            pick = team1 if p1n > p2n else team2

            ml_pretty = f"{team1}:{odds1} | {team2}:{odds2}"
            rows.append({
                "Sport": sport.split("_")[-1].upper(),
                "GameTime": ev.get("commence_time",""),
                "Team1": team1,
                "Team2": team2,
                "MoneylinePick": pick,
                "Confidence(%)": round(confidence, 2),
                "Edge": f"{implied_edge:.4f}%",
                "ML": ml_pretty,
                "ATS": "",
                "OU": "",
                "Reason": "Model vs Market probability differential",
                "LockEmoji": "🔒" if implied_edge > cfg["LOCK_EDGE_THRESHOLD"] and confidence > cfg["LOCK_CONFIDENCE_THRESHOLD"] else "",
                "UpsetEmoji": "💥" if implied_edge > cfg["UPSET_EDGE_THRESHOLD"] and confidence < 50 else ""
            })

            event_id = ev.get("id") or str(uuid.uuid4())
            hist_row = {
                "id": event_id,
                "sport": sport,
                "commence_time": ev.get("commence_time",""),
                "team1": team1,
                "team2": team2,
                "pick": pick,
                "pred_prob": max(p1n,p2n),
                "edge": implied_edge,
                "ml": ml_pretty,
                "ats": "",
                "ou": "",
                "reason": "Model vs Market probability differential",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "settled": False,
                "result": ""
            }
            append_history([hist_row])
            processed += 1
        except Exception as e:
            print("⚠️ Skipped event:", e)
            skipped += 1

# ---------- WRITE OUTPUT ----------
if not rows:
    print("❌ No events processed")
else:
    df = pd.DataFrame(rows)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    dated_file = OUT_DIR / f"Predictions_{now}_Explained.csv"

    # Always write both the dated and the “latest” versions
    df.to_csv(dated_file, index=False)
    df.to_csv(LATEST_FILE, index=False)

    unique_sports = sorted(df["Sport"].unique())
    print(f"✅ Unique sports saved in CSV: {unique_sports}")
    print(f"✅ Saved both: {dated_file} and {LATEST_FILE} (rows={len(df)})")
    print("🚀 Done — ready for web display.")
