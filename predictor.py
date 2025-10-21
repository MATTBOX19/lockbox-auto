# predictor_auto.py  (use instead of the previous predictor or merge)
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

# defaults (will be persisted)
DEFAULTS = {
    "ADJUST_FACTOR": 0.35,
    "LOCK_EDGE_THRESHOLD": 0.5,
    "LOCK_CONFIDENCE_THRESHOLD": 51.0,
    "UPSET_EDGE_THRESHOLD": 0.3,
    "calibrate_lr": 0.05,   # learning rate for simple online adjust
    "calibrate_window": 500 # how many recent settled rows to use
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
            print("⚠️ Failed load config:", e)
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

# API config / sports
API_KEY = os.getenv("ODDS_API_KEY")
REGION = "us"
MARKETS = "h2h,spreads,totals"
ODDS_API_URL = "https://api.the-odds-api.com/v4/sports/{sport}/odds"
SPORTS = ["americanfootball_nfl", "americanfootball_ncaaf", "basketball_nba", "icehockey_nhl", "baseball_mlb"]

def american_to_prob(odds):
    if odds is None:
        return None
    try:
        o = float(odds)
        if o > 0:
            return 100.0 / (o + 100.0)
        return -o / (-o + 100.0)
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
        print("⚠️ fetch error", e)
        return []

def append_history(rows):
    """Append rows (list of dicts) to history CSV; keep columns stable."""
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

def try_fetch_results_and_mark_history():
    """
    Starter: look for results by event id using The Odds API's 'scores' or 'events' result endpoints.
    You must implement result mapping — here we just provide the hook.
    """
    if not HISTORY_FILE.exists():
        return
    h = pd.read_csv(HISTORY_FILE)
    unsettled = h[h["settled"] != True]
    if unsettled.empty:
        print("No unsettled rows to reconcile")
        return

    # Example: For each unsettled row, call an API (pseudo).
    # This code is placeholder: replace with real result fetch logic or manual import.
    updates = []
    for idx, row in unsettled.iterrows():
        # pseudo: if commence_time in past by >4 hours mark as NEEDS_MANUAL
        try:
            ct = row.get("commence_time")
            if not ct:
                continue
            # simple rule: if time is >6 hours ago, mark as NEEDS_MANUAL
            dt = datetime.fromisoformat(ct.replace("Z","+00:00"))
            if (datetime.now(timezone.utc) - dt).total_seconds() > 6*3600:
                updates.append((idx, True, "NEEDS_MANUAL"))
        except Exception:
            continue

    if updates:
        for idx, settled, result in updates:
            h.loc[idx, "settled"] = True
            h.loc[idx, "result"] = result
        h.to_csv(HISTORY_FILE, index=False)
        print("✅ Marked some history rows as settled (placeholder, please replace with real settlement process)")

def auto_calibrate():
    """
    Very simple calibration: compute average predicted probability vs empirical win rate
    on most recent N settled rows and nudge ADJUST_FACTOR to reduce bias.

    ADJUST_FACTOR' = ADJUST_FACTOR * (1 + lr * (empirical_mean - predicted_mean) / predicted_mean)
    (keeps adjustment small and stable)
    """
    if not HISTORY_FILE.exists():
        print("No history for calibration")
        return
    h = pd.read_csv(HISTORY_FILE)
    # only rows with numeric pred_prob and settled=TRUE and result in {WIN,LOSS}
    settled = h[(h["settled"]==True) & (h["result"].notnull())]
    if settled.empty:
        print("No settled rows with results for calibration")
        return

    # But we need rows where result indicates whether pick actually won.
    # Expect result column to be "WIN" or "LOSS" or other markers.
    recent = settled.tail(int(cfg.get("calibrate_window", 500)))
    # compute empirical win rate on picks
    valid = recent[recent["pred_prob"].notnull()]
    if valid.empty:
        print("No valid rows for calibration")
        return

    # convert results to 1/0 if possible
    def as_win(res):
        if pd.isna(res): return None
        s = str(res).upper()
        if s in ("WIN","W","1","TRUE","HOME","AWAY"): # you will want to adjust mapping
            return 1
        if s in ("LOSS","L","0","FALSE"):
            return 0
        # unknown
        return None

    valid["winflag"] = valid["result"].apply(as_win)
    valid = valid[valid["winflag"].notna()]
    if valid.empty:
        print("No rows with interpretable results for calibration")
        return

    predicted_mean = valid["pred_prob"].astype(float).mean()
    empirical_mean = valid["winflag"].astype(float).mean()
    if predicted_mean <= 0:
        print("Bad predicted mean, abort calibrate")
        return

    error = empirical_mean - predicted_mean
    lr = float(cfg.get("calibrate_lr", 0.05))
    factor = cfg.get("ADJUST_FACTOR", ADJUST_FACTOR)
    # nudge factor: if model underestimates actual wins, increase adjust factor a bit
    new_factor = factor * (1 + lr * (error / predicted_mean))
    # clamp to reasonable bounds
    new_factor = max(0.01, min(new_factor, 2.0))
    cfg["ADJUST_FACTOR"] = new_factor
    save_config(cfg)
    print(f"🔧 Calibrated ADJUST_FACTOR: old={factor:.4f} new={new_factor:.4f} (error={error:.4f})")

# ----- main prediction loop (single run) -----
rows = []
processed = 0
skipped = 0

for sport in SPORTS:
    events = fetch_odds(sport)
    for ev in events:
        try:
            # robustly find home/away in v4
            home = ev.get("home_team") or ev.get("home")
            away = ev.get("away_team") or ev.get("away")
            # bookies may be empty
            bms = ev.get("bookmakers", [])
            if not bms:
                skipped += 1
                continue
            # find h2h market if present
            bm = bms[0]
            market = None
            for m in bm.get("markets", []):
                if m.get("key") == "h2h":
                    market = m
                    break
            if not market:
                # skip events with no h2h
                print(f"⚠️ Skipping event (no h2h market) id={ev.get('id')} available_markets={[m.get('key') for m in bm.get('markets',[])]}")
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
                "ATS": "", "OU": "",
                "Reason": "Model vs Market probability differential",
                "LockEmoji": "🔒" if implied_edge > cfg["LOCK_EDGE_THRESHOLD"] and confidence > cfg["LOCK_CONFIDENCE_THRESHOLD"] else "",
                "UpsetEmoji": "💥" if implied_edge > cfg["UPSET_EDGE_THRESHOLD"] and confidence < 50 else ""
            })

            # append to history row
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

# write latest CSV as before — but also dated copy for web compatibility
if not rows:
    print("❌ No events processed")
else:
    df = pd.DataFrame(rows)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    dated_file = OUT_DIR / f"Predictions_{now}_Explained.csv"
    df.to_csv(LATEST_FILE, index=False)
    df.to_csv(dated_file, index=False)
    unique_sports = sorted(df["Sport"].unique())
    print(f"✅ Unique sports saved in CSV: {unique_sports}")
    print(f"✅ Saved predictions to {dated_file} and {LATEST_FILE} (rows={len(df)})")
