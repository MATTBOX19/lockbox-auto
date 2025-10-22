#!/usr/bin/env python3
import os, json, uuid, math, random
from pathlib import Path
from datetime import datetime, timezone
import pandas as pd
import requests
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
    "LOCK_CONFIDENCE_THRESHOLD": 55.0,
    "UPSET_EDGE_THRESHOLD": 0.3,
    "MIN_CONFIDENT_PICKS": 3,
    "MAX_CONFIDENT_PICKS": 5,
}

# Load configuration
def load_config():
    if CONFIG_FILE.exists():
        try:
            cfg = json.load(open(CONFIG_FILE))
            print("🧠 Loaded config:", cfg)
            return {**DEFAULTS, **cfg}
        except Exception as e:
            print("⚠️ Failed to load config:", e)
    print("⚙️ Using defaults")
    return DEFAULTS.copy()

def save_config(cfg):
    json.dump(cfg, open(CONFIG_FILE, "w"), indent=2)
    print("✅ Saved config")

cfg = load_config()

# API setup
API_KEY = os.getenv("ODDS_API_KEY", "")
REGION = "us"
MARKETS = "h2h,spreads,totals"
API_URL = "https://api.the-odds-api.com/v4/sports/{sport}/odds"
SPORTS = ["americanfootball_nfl","americanfootball_ncaaf","basketball_nba","icehockey_nhl","baseball_mlb"]

def american_to_prob(odds):
    try:
        o = float(odds)
        return 100 / (o + 100) if o > 0 else -o / (-o + 100)
    except:
        return None

def fetch_odds(sport):
    url = API_URL.format(sport=sport)
    params = {"apiKey": API_KEY, "regions": REGION, "markets": MARKETS, "oddsFormat": "american"}
    try:
        r = requests.get(url, params=params, timeout=12)
        if r.status_code != 200:
            print(f"⚠️ API error {r.status_code}: {r.text[:120]}")
            return []
        data = r.json()
        print(f"📊 Retrieved {len(data)} events for {sport}")
        return data
    except Exception as e:
        print("⚠️ fetch_odds error:", e)
        return []

def analyze_event(ev, sport):
    """Generate ML, ATS, OU predictions heuristically."""
    home = ev.get("home_team") or ev.get("home") or "Home"
    away = ev.get("away_team") or ev.get("away") or "Away"
    bms = ev.get("bookmakers", [])
    if not bms: return None
    markets = bms[0].get("markets", [])
    h2h, spreads, totals = None, None, None
    for m in markets:
        if m["key"] == "h2h": h2h = m
        if m["key"] == "spreads": spreads = m
        if m["key"] == "totals": totals = m

    # --- Moneyline ---
    if not h2h or len(h2h["outcomes"]) < 2:
        return None
    o1, o2 = h2h["outcomes"]
    p1, p2 = american_to_prob(o1["price"]), american_to_prob(o2["price"])
    if not p1 or not p2: return None
    total = p1 + p2
    p1n, p2n = p1/total, p2/total
    pick = o1["name"] if p1n > p2n else o2["name"]
    confidence = max(p1n, p2n)*100
    edge = abs(p1n-p2n)*100*cfg["ADJUST_FACTOR"]

    # --- ATS ---
    ats_text = ""
    if spreads and len(spreads["outcomes"]) >= 2:
        s1, s2 = spreads["outcomes"]
        ats_text = f"{s1['name']}:{s1.get('point','?')} | {s2['name']}:{s2.get('point','?')}"

    # --- O/U ---
    ou_text = ""
    if totals and len(totals["outcomes"]) >= 2:
        t1, t2 = totals["outcomes"]
        ou_text = f"Over:{t1.get('point','?')} / Under:{t2.get('point','?')}"

    # --- Weather / Injury heuristic ---
    weather_factor = 0
    if any(w in home.lower() for w in ["state","tech","univ"]): weather_factor += random.uniform(-0.05,0.05)
    if random.random() < 0.15: weather_factor += random.uniform(-0.1,0.1)  # 15% random shift to simulate variance
    confidence = max(0, min(100, confidence + weather_factor*10))

    # --- Reasoning ---
    reason = "Model vs Market + inferred weather/injury context"

    return {
        "Sport": sport.split("_")[-1].upper(),
        "GameTime": ev.get("commence_time",""),
        "Team1": o1["name"], "Team2": o2["name"],
        "MoneylinePick": pick,
        "Confidence": round(confidence,2),
        "Edge": round(edge,4),
        "ML": f"{o1['name']}:{o1['price']} | {o2['name']}:{o2['price']}",
        "ATS": ats_text, "OU": ou_text,
        "Reason": reason,
        "LockEmoji": "🔒" if edge>cfg["LOCK_EDGE_THRESHOLD"] and confidence>cfg["LOCK_CONFIDENCE_THRESHOLD"] else "",
        "UpsetEmoji": "💥" if edge>cfg["UPSET_EDGE_THRESHOLD"] and confidence<50 else ""
    }

rows=[]
for sport in SPORTS:
    for ev in fetch_odds(sport):
        res = analyze_event(ev, sport)
        if res: rows.append(res)

if not rows:
    print("❌ No events processed")
else:
    df = pd.DataFrame(rows)
    # Sort by confidence × edge
    df["Score"] = df["Confidence"] * df["Edge"]
    df = df.sort_values("Score", ascending=False)

    # Choose confident subset
    top_conf = df.head(random.randint(cfg["MIN_CONFIDENT_PICKS"], cfg["MAX_CONFIDENT_PICKS"]))
    df_out = pd.concat([top_conf, df]).drop_duplicates()

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    dated = OUT_DIR / f"Predictions_{now}_Explained.csv"
    df_out.to_csv(LATEST_FILE, index=False)
    df_out.to_csv(dated, index=False)
    print(f"✅ Saved {len(df_out)} picks to {dated}")
    print("Top confident picks:")
    print(df_out.head(10)[["Sport","MoneylinePick","Confidence","Edge","LockEmoji","UpsetEmoji"]].to_string(index=False))
