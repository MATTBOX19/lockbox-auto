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

# ------------------- Default Config -------------------
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

cfg = load_config()

ADJUST_FACTOR = cfg["ADJUST_FACTOR"]
LOCK_EDGE_THRESHOLD = cfg["LOCK_EDGE_THRESHOLD"]
LOCK_CONFIDENCE_THRESHOLD = cfg["LOCK_CONFIDENCE_THRESHOLD"]
UPSET_EDGE_THRESHOLD = cfg["UPSET_EDGE_THRESHOLD"]

# ------------------- API Config -------------------
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

# ------------------- Helper Functions -------------------
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

# ------------------- Main Prediction Loop -------------------
rows = []
history_rows = []

for sport in SPORTS:
    events = fetch_odds(sport)
    for ev in events:
        try:
            home = ev.get("home_team") or ev.get("home")
            away = ev.get("away_team") or ev.get("away")
            bms = ev.get("bookmakers", [])
            if not bms:
                continue
            bm = bms[0]

            # ---- Markets ----
            h2h = next((m for m in bm.get("markets", []) if m.get("key") == "h2h"), None)
            spreads = next((m for m in bm.get("markets", []) if m.get("key") == "spreads"), None)
            totals = next((m for m in bm.get("markets", []) if m.get("key") == "totals"), None)

            if not h2h or len(h2h.get("outcomes", [])) != 2:
                continue
            o1, o2 = h2h["outcomes"]
            team1, team2 = o1["name"], o2["name"]
            odds1, odds2 = o1["price"], o2["price"]
            p1, p2 = american_to_prob(odds1), american_to_prob(odds2)
            if not p1 or not p2:
                continue

            total = p1 + p2
            p1n, p2n = p1 / total, p2 / total
            implied_edge = abs(p1n - p2n) * 100 * ADJUST_FACTOR
            confidence = max(p1n, p2n) * 100
            pick = team1 if p1n > p2n else team2

            # ---- Spreads ----
            ats_str = ""
            if spreads and len(spreads.get("outcomes", [])) == 2:
                so1, so2 = spreads["outcomes"]
                ats_str = f"{so1['name']}:{so1.get('point')} | {so2['name']}:{so2.get('point')}"

            # ---- Totals ----
            ou_str = ""
            if totals and len(totals.get("outcomes", [])) == 2:
                to1, to2 = totals["outcomes"]
                ou_str = f"{to1['name']}:{to1.get('point')} / {to2['name']}:{to2.get('point')}"

            ml_str = f"{team1}:{odds1} | {team2}:{odds2}"

            rows.append({
                "Sport": sport.split("_")[-1].upper(),
                "GameTime": ev.get("commence_time",""),
                "Team1": team1,
                "Team2": team2,
                "MoneylinePick": pick,
                "Confidence": round(confidence, 2),
                "Edge": round(implied_edge, 4),
                "ML": ml_str,
                "ATS": ats_str,
                "OU": ou_str,
                "Reason": "Model vs Market probability differential",
                "LockEmoji": "",
                "UpsetEmoji": ""
            })

            event_id = ev.get("id") or str(uuid.uuid4())
            history_rows.append({
                "id": event_id,
                "sport": sport,
                "commence_time": ev.get("commence_time",""),
                "team1": team1,
                "team2": team2,
                "pick": pick,
                "pred_prob": max(p1n,p2n),
                "edge": implied_edge,
                "ml": ml_str,
                "ats": ats_str,
                "ou": ou_str,
                "reason": "Model vs Market probability differential",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "settled": False,
                "result": ""
            })

        except Exception as e:
            print("⚠️ Skipped event:", e)

# ------------------- Lock & Upset Assignment -------------------
if rows:
    df = pd.DataFrame(rows)
    df["LockScore"] = df["Confidence"] * df["Edge"]
    df = df.sort_values("LockScore", ascending=False)

    # pick top 5 overall
    top5_idx = df.head(5).index

    for i, r in df.iterrows():
        edge = float(r["Edge"])
        conf = float(r["Confidence"])

        # convert threshold to same % scale
        lock = (i in top5_idx) or (edge > (LOCK_EDGE_THRESHOLD * 100) and conf > LOCK_CONFIDENCE_THRESHOLD)
        upset = (edge > (UPSET_EDGE_THRESHOLD * 100) and conf < 50)

        df.at[i, "LockEmoji"] = "🔒" if lock else ""
        df.at[i, "UpsetEmoji"] = "💥" if upset else ""

    df = df.drop(columns=["LockScore"])

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    dated_file = OUT_DIR / f"Predictions_{now}_Explained.csv"
    df.to_csv(dated_file, index=False)
    df.to_csv(LATEST_FILE, index=False)

    append_history(history_rows)
    print(f"✅ Unique sports saved in CSV: {sorted(df['Sport'].unique())}")
    print(f"✅ Saved predictions to {dated_file} and {LATEST_FILE} (rows={len(df)})")
else:
    print("❌ No events processed")

print("🚀 Done — ready for web display.")
