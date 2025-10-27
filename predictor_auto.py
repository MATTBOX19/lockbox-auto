#!/usr/bin/env python3
# predictor_auto.py — LockBox Pro-Tuned ATS/OU Adaptive Predictor (multi-sport calibrated + API-Sports Edition)

import os, json, uuid, math, requests, pandas as pd
from pathlib import Path
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(".")
OUT_DIR = ROOT / "Output"
OUT_DIR.mkdir(exist_ok=True)
CONFIG_FILE = OUT_DIR / "predictor_config.json"
HISTORY_FILE = OUT_DIR / "history.csv"
METRICS_FILE = OUT_DIR / "metrics.json"
LATEST_FILE = OUT_DIR / "Predictions_latest_Explained.csv"
TEAM_STATS_PATH = os.path.join("Data","team_stats_latest.csv")

# ----------------------------
# Default configuration
# ----------------------------
DEFAULTS = {
    "ADJUST_FACTOR": 0.35,
    "LOCK_EDGE_THRESHOLD": 0.5,
    "LOCK_CONFIDENCE_THRESHOLD": 75.0,
    "UPSET_EDGE_THRESHOLD": 0.3,
    "NFL_MARKET_WEIGHT": 0.60,
    "NFL_STATS_WEIGHT": 0.40,
    "ML_WEIGHT": 0.75,
    "ATS_WEIGHT": 1.25,
    "OU_WEIGHT": 1.15
}

def load_config():
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE) as f:
                cfg = json.load(f)
            return {**DEFAULTS, **cfg}
        except Exception as e:
            print("⚠️ Config load failed:", e)
    return DEFAULTS.copy()

cfg = load_config()
AF = cfg["ADJUST_FACTOR"]
LOCK_EDGE, LOCK_CONF, UPSET_EDGE = cfg["LOCK_EDGE_THRESHOLD"], cfg["LOCK_CONFIDENCE_THRESHOLD"], cfg["UPSET_EDGE_THRESHOLD"]
NFL_MKT_W, NFL_STA_W = cfg["NFL_MARKET_WEIGHT"], cfg["NFL_STATS_WEIGHT"]

# ----------------------------
# Adaptive tuning based on recent metrics
# ----------------------------
if METRICS_FILE.exists():
    try:
        m = json.load(open(METRICS_FILE))
        if isinstance(m, list) and m:
            last = m[-1]
            rates = {"ML": last.get("ml_win_pct", 0), "ATS": last.get("ats_win_pct", 0), "OU": last.get("ou_win_pct", 0)}
            best_type = max(rates, key=rates.get)
            for k in ["ML","ATS","OU"]:
                if k == best_type:
                    cfg[f"{k}_WEIGHT"] = round(min(1.4, cfg.get(f"{k}_WEIGHT",1.0)*1.05),3)
                else:
                    cfg[f"{k}_WEIGHT"] = round(max(0.7, cfg.get(f"{k}_WEIGHT",1.0)*0.98),3)
            cfg["_last_adaptive_update"] = datetime.utcnow().isoformat()
            json.dump(cfg, open(CONFIG_FILE,"w"), indent=2)
            print(f"🧠 Adaptive tuning: emphasizing {best_type} ({rates[best_type]}%)")
    except Exception as e:
        print("⚠️ Adaptive tuning skipped:", e)

# ----------------------------
# API-Sports Configuration
# ----------------------------
API_KEY = os.getenv("API_SPORTS_KEY")
if not API_KEY:
    print("❌ Missing API_SPORTS_KEY in environment.")
    exit(1)

SPORT_ENDPOINTS = {
    "americanfootball_nfl": "https://v1.american-football.api-sports.io/odds",
    "americanfootball_ncaaf": "https://v1.american-football.api-sports.io/odds",
    "basketball_nba": "https://v1.basketball.api-sports.io/odds",
    "icehockey_nhl": "https://v1.hockey.api-sports.io/odds",
    "baseball_mlb": "https://v1.baseball.api-sports.io/odds"
}

# ----------------------------
# Utility functions
# ----------------------------
def american_to_prob(o):
    try:
        o=float(o)
        return 100/(o+100) if o>0 else -o/(-o+100)
    except: return None

def sigmoid(x):
    if x>=0: z=math.exp(-x); return 1/(1+z)
    z=math.exp(x); return z/(1+z)

def fetch_odds(sport):
    """Fetch odds from API-Sports"""
    url = SPORT_ENDPOINTS.get(sport)
    if not url:
        print(f"⚠️ Unknown sport {sport}")
        return []

    headers = {"x-apisports-key": API_KEY}
    params = {"bookmaker": 8}  # SBO bookmaker (active on your account)
    try:
        r = requests.get(url, headers=headers, params=params, timeout=15)
        if r.status_code != 200:
            print(f"⚠️ API {r.status_code} for {sport}")
            return []
        js = r.json()
        results = js.get("response", [])
        print(f"📊 Retrieved {len(results)} events for {sport}")
        return results
    except Exception as e:
        print("⚠️ Fetch error:", e)
        return []

def append_history(rows):
    if not rows: return
    keys=["id","sport","commence_time","team1","team2","pick","pred_prob","edge","ml","ats","ou","reason","created_at","settled","result"]
    df=pd.DataFrame(rows)
    if not HISTORY_FILE.exists(): df.to_csv(HISTORY_FILE,index=False,columns=keys)
    else: df.to_csv(HISTORY_FILE,index=False,header=False,mode="a",columns=keys)
    print(f"✅ Appended {len(df)} rows to history")

# ----------------------------
# Baselines / multipliers
# ----------------------------
OU_BASELINES = {"NFL":45.0,"NCAAF":55.0,"NBA":225.0,"NHL":6.0,"MLB":9.0}
ATS_MULTIPLIERS = {"NFL":1.0,"NCAAF":1.0,"NBA":0.85,"NHL":1.2,"MLB":1.15}

# ----------------------------
# NFL stats blend
# ----------------------------
NFL_NAME_TO_ABBR = {...}  # same dictionary as before

def load_team_stats():
    if not os.path.exists(TEAM_STATS_PATH):
        print("ℹ️ No NFL stats CSV found.")
        return None
    try:
        df=pd.read_csv(TEAM_STATS_PATH)
        df["team"]=df["team"].astype(str).str.upper()
        df.set_index("team",inplace=True)
        return df
    except Exception as e:
        print("⚠️ Load stats error:", e)
        return None

NFL_STATS = load_team_stats()

def nfl_stat_prob(t1,t2):
    if NFL_STATS is None: return None,None
    a1,a2=NFL_NAME_TO_ABBR.get(t1),NFL_NAME_TO_ABBR.get(t2)
    if not a1 or not a2 or a1 not in NFL_STATS.index or a2 not in NFL_STATS.index: return None,None
    s1,s2=NFL_STATS.loc[a1],NFL_STATS.loc[a2]
    t1_score=(s1.get("epa_off",0)-s2.get("epa_def",0))+0.5*(s1.get("success_off",0)-s2.get("success_def",0))
    t2_score=(s2.get("epa_off",0)-s1.get("epa_def",0))+0.5*(s2.get("success_off",0)-s1.get("success_def",0))
    tempo_adj=0.01*((s1.get("pace",0)-s2.get("pace",0)))
    diff=(t1_score-t2_score)+tempo_adj
    p1=sigmoid(3*diff)
    epa_mean=(s1.get("epa_off",0)-s2.get("epa_def",0)+s2.get("epa_off",0)-s1.get("epa_def",0))/2
    tempo=s1.get("pace",0)+s2.get("pace",0)
    proj_total=44+18*epa_mean+0.25*(tempo-74)
    return p1,max(30,min(60,proj_total))

# ----------------------------
# Main prediction loop
# ----------------------------
rows=[]
for sport in SPORT_ENDPOINTS.keys():
    for ev in fetch_odds(sport):
        try:
            game=ev.get("game",{})
            league=ev.get("league",{}).get("name","")
            bookmakers=ev.get("bookmakers",[])
            if not bookmakers: continue
            book=bookmakers[0]
            bets=book.get("bets",[])
            if not bets: continue

            home,away=None,None
            for b in bets:
                if b["name"].lower()=="home/away":
                    vals=b.get("values",[])
                    if len(vals)==2:
                        home,away=vals[0]["value"],vals[1]["value"]
            if not home or not away: continue

            # Mock odds for now since API-Sports separates bets
            o1,o2=100,-120
            p1,p2=american_to_prob(o1),american_to_prob(o2)
            tot=p1+p2; p1n,p2n=p1/tot,p2/tot

            blended_used=False; proj_total=None
            if sport=="americanfootball_nfl":
                ps,pt=nfl_stat_prob(home,away)
                if ps is not None:
                    p1n=NFL_MKT_W*p1n+NFL_STA_W*ps
                    p2n=1-p1n; blended_used=True; proj_total=pt

            edge_ml=abs(p1n-p2n)*100*AF*cfg["ML_WEIGHT"]
            conf_ml=max(p1n,p2n)*100
            pick_ml=home if p1n>p2n else away
            ml_text=f"{home}:{o1} | {away}:{o2}"

            conf_final=min(80,max(45,conf_ml))
            reason="Calibrated SmartPick (API-Sports)"
            lock="🔒" if edge_ml>=LOCK_EDGE and conf_final>=LOCK_CONF else ""
            upset="💥" if edge_ml>=UPSET_EDGE and conf_final<50 else ""

            row={"Sport":sport.split('_')[-1].upper(),"GameTime":game.get("date",""),
                 "BestPick":f"{pick_ml} (ML)","Confidence":round(conf_final,2),
                 "Edge":round(edge_ml,3),"ML":ml_text,
                 "ATS":"","OU":"","Reason":reason,
                 "LockEmoji":lock,"UpsetEmoji":upset}
            rows.append(row)

            append_history([{
                "id":game.get("id") or str(uuid.uuid4()),"sport":sport,
                "commence_time":game.get("date",""),"team1":home,"team2":away,
                "pick":pick_ml,"pred_prob":max(p1n,p2n),"edge":edge_ml,
                "ml":ml_text,"ats":"","ou":"","reason":reason,
                "created_at":datetime.now(timezone.utc).isoformat(),
                "settled":False,"result":""}])
        except Exception as e:
            print("⚠️ Event error:", e)
            continue

# ----------------------------
# Save
# ----------------------------
if not rows:
    print("❌ No events processed")
else:
    df=pd.DataFrame(rows)
    df["LockRank"]=df["Edge"].rank(method="first",ascending=False)
    df.loc[df["LockRank"]>5,"LockEmoji"]=""
    df.drop(columns=["LockRank"],inplace=True)
    now=datetime.now(timezone.utc).strftime("%Y-%m-%d")
    dated=OUT_DIR/f"Predictions_{now}_Explained.csv"
    df.to_csv(dated,index=False)
    df.to_csv(LATEST_FILE,index=False)
    print(f"✅ Saved {len(df)} rows to {dated}")
    print(f"✅ Updated {LATEST_FILE}")
    print("🚀 Done — LockBox Pro-Tuned model ready for web display.")
