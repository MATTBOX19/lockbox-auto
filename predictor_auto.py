
#!/usr/bin/env python3
# predictor_auto.py — keeps all sports; adds NFL market+stats blended model

import os, json, uuid
from pathlib import Path
from datetime import datetime, timezone
import math
import requests
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

# -------------------------
# Paths & config
# -------------------------
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
    "calibrate_window": 500,
    # NFL blend weights
    "NFL_MARKET_WEIGHT": 0.60,
    "NFL_STATS_WEIGHT": 0.40
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
NFL_MKT_W = cfg["NFL_MARKET_WEIGHT"]
NFL_STA_W = cfg["NFL_STATS_WEIGHT"]

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

# -------------------------
# Helpers
# -------------------------
def american_to_prob(odds):
    if odds is None: return None
    try:
        o = float(odds)
        return 100.0 / (o + 100.0) if o > 0 else -o / (-o + 100.0)
    except:
        return None

def sigmoid(x):  # stable logistic
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    else:
        z = math.exp(x)
        return z / (1.0 + z)

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

# -------------------------
# NFL Team mapping & stats
# -------------------------
TEAM_STATS_PATH = os.path.join("Data","team_stats_latest.csv")

# Map common OddsAPI team names to our CSV abbreviations
NFL_NAME_TO_ABBR = {
    "Arizona Cardinals": "ARI",
    "Atlanta Falcons": "ATL",
    "Baltimore Ravens": "BAL",
    "Buffalo Bills": "BUF",
    "Carolina Panthers": "CAR",
    "Chicago Bears": "CHI",
    "Cincinnati Bengals": "CIN",
    "Cleveland Browns": "CLE",
    "Dallas Cowboys": "DAL",
    "Denver Broncos": "DEN",
    "Detroit Lions": "DET",
    "Green Bay Packers": "GB",
    "Houston Texans": "HOU",
    "Indianapolis Colts": "IND",
    "Jacksonville Jaguars": "JAX",
    "Kansas City Chiefs": "KC",
    "Las Vegas Raiders": "LV",
    "Los Angeles Chargers": "LAC",
    "Los Angeles Rams": "LAR",
    "Miami Dolphins": "MIA",
    "Minnesota Vikings": "MIN",
    "New England Patriots": "NE",
    "New Orleans Saints": "NO",
    "New York Giants": "NYG",
    "New York Jets": "NYJ",
    "Philadelphia Eagles": "PHI",
    "Pittsburgh Steelers": "PIT",
    "San Francisco 49ers": "SF",
    "Seattle Seahawks": "SEA",
    "Tampa Bay Buccaneers": "TB",
    "Tennessee Titans": "TEN",
    "Washington Commanders": "WAS",
}

def load_team_stats():
    if not os.path.exists(TEAM_STATS_PATH):
        print("ℹ️ NFL stats CSV not found — using market-only for NFL.")
        return None
    try:
        df = pd.read_csv(TEAM_STATS_PATH)
        # normalize abbreviation column to upper strings
        df["team"] = df["team"].astype(str).str.upper()
        df.set_index("team", inplace=True)
        return df
    except Exception as e:
        print(f"⚠️ Failed to load NFL stats: {e}")
        return None

NFL_STATS = load_team_stats()

def get_abbr(team_name: str):
    return NFL_NAME_TO_ABBR.get(team_name)

def nfl_stat_prob(team1_name: str, team2_name: str):
    """Return (p_team1_stats, projected_total_points) if stats available, else (None, None)."""
    if NFL_STATS is None:
        return None, None
    a1 = get_abbr(team1_name)
    a2 = get_abbr(team2_name)
    if not a1 or not a2:  # if we cannot map, bail out
        return None, None
    if a1 not in NFL_STATS.index or a2 not in NFL_STATS.index:
        return None, None

    t1 = NFL_STATS.loc[a1]
    t2 = NFL_STATS.loc[a2]

    # Simple composite scores (offense vs opponent defense + success + tempo)
    # You can tweak weights safely later.
    t1_score = (t1.get("epa_off", 0) - t2.get("epa_def", 0)) + 0.5*(t1.get("success_off",0) - t2.get("success_def",0))
    t2_score = (t2.get("epa_off", 0) - t1.get("epa_def", 0)) + 0.5*(t2.get("success_off",0) - t1.get("success_def",0))
    tempo_adj = 0.01*((t1.get("pace",0) - t2.get("pace",0)))

    diff = (t1_score - t2_score) + tempo_adj

    # Convert diff into probability via logistic; scale so typical diffs map to reasonable spreads
    k = 3.0  # sensitivity
    p_t1 = sigmoid(k*diff)

    # Projected total: base ~44 plus EPA & tempo influences
    epa_mean = (t1.get("epa_off",0) - t2.get("epa_def",0) + t2.get("epa_off",0) - t1.get("epa_def",0)) / 2.0
    tempo = (t1.get("pace",0) + t2.get("pace",0))  # typical sum ~ 72–78 in our sample CSV
    proj_total = 44.0 + 18.0*epa_mean + 0.25*(tempo - 74.0)

    # Clamp projected total to sane bounds
    proj_total = max(30.0, min(60.0, proj_total))

    return p_t1, proj_total

# -------------------------
# Main: build rows
# -------------------------
rows = []

for sport in SPORTS:
    events = fetch_odds(sport)
    for ev in events:
        try:
            home = ev.get("home_team") or ev.get("home")
            away = ev.get("away_team") or ev.get("away")
            if not home or not away:
                continue

            bm = ev.get("bookmakers", [{}])[0]
            markets = {m["key"]: m for m in bm.get("markets", [])}

            # --- Moneyline (H2H) ---
            h2h = markets.get("h2h")
            if not h2h:
                print(f"⚠️ Skipping event (no h2h market) id={ev.get('id')}")
                continue
            outcomes = h2h.get("outcomes", [])
            if len(outcomes) != 2:
                continue

            team1, team2 = outcomes[0]["name"], outcomes[1]["name"]
            odds1, odds2 = outcomes[0]["price"], outcomes[1]["price"]

            p1 = american_to_prob(odds1)
            p2 = american_to_prob(odds2)
            if not p1 or not p2:
                continue

            total = p1 + p2
            p1n, p2n = p1 / total, p2 / total  # market-normalized

            # ---------- NFL blend (market + stats) ----------
            blended_used = False
            proj_total_from_stats = None
            if sport == "americanfootball_nfl":
                p_stats_t1, proj_total_from_stats = nfl_stat_prob(team1, team2)
                if p_stats_t1 is not None:
                    p1b = NFL_MKT_W * p1n + NFL_STA_W * p_stats_t1
                    p2b = 1.0 - p1b
                    p1n, p2n = p1b, p2b
                    blended_used = True

            # Edge / confidence / pick
            edge = abs(p1n - p2n) * 100 * ADJUST_FACTOR
            confidence = max(p1n, p2n) * 100
            pick_ml = team1 if p1n > p2n else team2
            ml_pretty = f"{team1}:{odds1} | {team2}:{odds2}"

            # --- ATS (spread) ---
            ats = markets.get("spreads")
            pick_ats, ats_pretty = "", ""
            if ats:
                outcomes_ats = ats.get("outcomes", [])
                if len(outcomes_ats) == 2:
                    s1, s2 = outcomes_ats[0].get("point"), outcomes_ats[1].get("point")
                    if s1 is not None and s2 is not None:
                        # Use blended probabilities if NFL to infer implied margin
                        implied_margin = (p1n - p2n) * 100 / 2.5
                        team1_cover_diff = implied_margin + s1
                        team2_cover_diff = -implied_margin + s2
                        pick_ats = team1 if abs(team1_cover_diff) < abs(team2_cover_diff) else team2
                        ats_pretty = f"{team1}:{s1} | {team2}:{s2}"

            # --- Over/Under ---
            ou = markets.get("totals")
            pick_ou, ou_pretty = "", ""
            if ou:
                outcomes_ou = ou.get("outcomes", [])
                if len(outcomes_ou) == 2:
                    line_pts = outcomes_ou[0].get("point")
                    if line_pts:
                        # If we have an NFL stat projection, use it; else keep previous simple logic.
                        if blended_used and proj_total_from_stats is not None:
                            pick_ou = "Over" if proj_total_from_stats > float(line_pts) else "Under"
                        else:
                            implied_total = (p1n + p2n) * 50  # legacy heuristic
                            pick_ou = "Over" if implied_total > float(line_pts) else "Under"
                        ou_pretty = f"Over:{line_pts} / Under:{line_pts}"

            # --- Emoji Flags ---
            lock_flag = "🔒" if (edge >= LOCK_EDGE_THRESHOLD and confidence >= LOCK_CONFIDENCE_THRESHOLD) else ""
            upset_flag = "💥" if (edge >= UPSET_EDGE_THRESHOLD and confidence < 50) else ""

            reason = (
                "NFL blended (market+team stats)"
                if (sport == "americanfootball_nfl" and blended_used)
                else "Simulated market differential model"
            )

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
                "Reason": reason,
                "LockEmoji": lock_flag,
                "UpsetEmoji": upset_flag
            }
            rows.append(row)

            # history
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
                "reason": reason,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "settled": False,
                "result": ""
            }])

        except Exception as e:
            print("⚠️ Event error:", e)
            continue

# -------------------------
# Save outputs
# -------------------------
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
