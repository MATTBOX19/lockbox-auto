#!/usr/bin/env python3
# predictor_auto.py — adaptive LockBox predictor (market+stats blend + self-tuning)

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

DEFAULTS = {
    "ADJUST_FACTOR": 0.35,
    "LOCK_EDGE_THRESHOLD": 0.5,
    "LOCK_CONFIDENCE_THRESHOLD": 75.0,
    "UPSET_EDGE_THRESHOLD": 0.3,
    "NFL_MARKET_WEIGHT": 0.60,
    "NFL_STATS_WEIGHT": 0.40,
    "ML_WEIGHT": 1.0,
    "ATS_WEIGHT": 1.0,
    "OU_WEIGHT": 1.0
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

# --- Adaptive tuning ---
if METRICS_FILE.exists():
    try:
        m = json.load(open(METRICS_FILE))
        if isinstance(m, list) and m:
            last = m[-1]
            rates = {
                "ML": last.get("ml_win_pct", 0),
                "ATS": last.get("ats_win_pct", 0),
                "OU": last.get("ou_win_pct", 0)
            }
            best_type = max(rates, key=rates.get)
            best_rate = rates[best_type]
            # normalize weights (max 1.25x)
            for k in ["ML", "ATS", "OU"]:
                cfg[f"{k}_WEIGHT"] = 1.25 if k == best_type else 1.0
            print(f"🧠 Adaptive tuning: now favoring {best_type} (win rate {best_rate}%)")
            with open(CONFIG_FILE, "w") as f:
                json.dump(cfg, f, indent=2)
    except Exception as e:
        print("⚠️ Adaptive tuning skipped:", e)

API_KEY = os.getenv("ODDS_API_KEY")
REGION, MARKETS = "us", "h2h,spreads,totals"
SPORTS = ["americanfootball_nfl","americanfootball_ncaaf","basketball_nba","icehockey_nhl","baseball_mlb"]
ODDS_API_URL = "https://api.the-odds-api.com/v4/sports/{sport}/odds"

def american_to_prob(o):
    try:
        o = float(o)
        return 100/(o+100) if o>0 else -o/(-o+100)
    except: return None

def sigmoid(x):
    if x>=0:
        z=math.exp(-x); return 1/(1+z)
    z=math.exp(x); return z/(1+z)

def fetch_odds(s):
    try:
        r=requests.get(ODDS_API_URL.format(sport=s),
            params={"apiKey":API_KEY,"regions":REGION,"markets":MARKETS,"oddsFormat":"american"},
            timeout=15)
        if r.status_code!=200:
            print(f"⚠️ API {r.status_code} {s}"); return []
        data=r.json(); print(f"📊 Retrieved {len(data)} events for {s}"); return data
    except Exception as e:
        print("⚠️ Fetch error:",e); return []

def append_history(rows):
    if not rows: return
    keys=["id","sport","commence_time","team1","team2","pick","pred_prob","edge","ml","ats","ou","reason","created_at","settled","result"]
    df=pd.DataFrame(rows)
    if not HISTORY_FILE.exists(): df.to_csv(HISTORY_FILE,index=False,columns=keys)
    else: df.to_csv(HISTORY_FILE,index=False,header=False,mode="a",columns=keys)
    print(f"✅ Appended {len(df)} rows to history")

NFL_NAME_TO_ABBR={
"Arizona Cardinals":"ARI","Atlanta Falcons":"ATL","Baltimore Ravens":"BAL","Buffalo Bills":"BUF","Carolina Panthers":"CAR",
"Chicago Bears":"CHI","Cincinnati Bengals":"CIN","Cleveland Browns":"CLE","Dallas Cowboys":"DAL","Denver Broncos":"DEN",
"Detroit Lions":"DET","Green Bay Packers":"GB","Houston Texans":"HOU","Indianapolis Colts":"IND","Jacksonville Jaguars":"JAX",
"Kansas City Chiefs":"KC","Las Vegas Raiders":"LV","Los Angeles Chargers":"LAC","Los Angeles Rams":"LAR","Miami Dolphins":"MIA",
"Minnesota Vikings":"MIN","New England Patriots":"NE","New Orleans Saints":"NO","New York Giants":"NYG","New York Jets":"NYJ",
"Philadelphia Eagles":"PHI","Pittsburgh Steelers":"PIT","San Francisco 49ers":"SF","Seattle Seahawks":"SEA","Tampa Bay Buccaneers":"TB",
"Tennessee Titans":"TEN","Washington Commanders":"WAS"}

def load_team_stats():
    if not os.path.exists(TEAM_STATS_PATH):
        print("ℹ️ No NFL stats CSV found."); return None
    try:
        df=pd.read_csv(TEAM_STATS_PATH)
        df["team"]=df["team"].astype(str).str.upper()
        df.set_index("team",inplace=True)
        return df
    except Exception as e:
        print("⚠️ Load stats error:",e)
        return None

NFL_STATS=load_team_stats()

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

rows=[]
for sport in SPORTS:
    for ev in fetch_odds(sport):
        try:
            home,away=ev.get("home_team"),ev.get("away_team")
            if not home or not away: continue
            bm=ev.get("bookmakers",[{}])[0]
            mk={m["key"]:m for m in bm.get("markets",[])}
            h2h=mk.get("h2h")
            if not h2h: continue
            outs=h2h.get("outcomes",[])
            if len(outs)!=2: continue
            t1,t2=outs[0]["name"],outs[1]["name"]
            o1,o2=outs[0]["price"],outs[1]["price"]
            p1,p2=american_to_prob(o1),american_to_prob(o2)
            if not p1 or not p2: continue
            tot=p1+p2; p1n,p2n=p1/tot,p2/tot
            blended_used=False; proj_total=None
            if sport=="americanfootball_nfl":
                ps,pt=nfl_stat_prob(t1,t2)
                if ps is not None:
                    p1n= NFL_MKT_W*p1n + NFL_STA_W*ps
                    p2n=1-p1n; blended_used=True; proj_total=pt
            edge_ml=abs(p1n-p2n)*100*AF
            conf_ml=max(p1n,p2n)*100
            pick_ml=t1 if p1n>p2n else t2
            ml_text=f"{t1}:{o1} | {t2}:{o2}"

            # --- ATS ---
            edge_ats=0; pick_ats=""; ats_text=""
            if mk.get("spreads"):
                outs_sp=mk["spreads"].get("outcomes",[])
                if len(outs_sp)==2:
                    s1,s2=outs_sp[0].get("point"),outs_sp[1].get("point")
                    if s1 is not None and s2 is not None:
                        implied=(p1n-p2n)*100/2.5
                        t1_diff=implied+s1; t2_diff=-implied+s2
                        pick_ats=t1 if abs(t1_diff)<abs(t2_diff) else t2
                        edge_ats=abs(t1_diff-t2_diff)
                        ats_text=f"{t1}:{s1} | {t2}:{s2}"

            # --- OU ---
            edge_ou=0; pick_ou=""; ou_text=""
            if mk.get("totals"):
                outs_ou=mk["totals"].get("outcomes",[])
                if len(outs_ou)==2:
                    line=float(outs_ou[0].get("point"))
                    exp=proj_total if blended_used and proj_total else (p1n+p2n)*50
                    diff=exp-line; edge_ou=abs(diff); pick_ou="Over" if diff>0 else "Under"
                    ou_text=f"Over:{line}/Under:{line}"

            # --- Adaptive weighting ---
            edge_ml *= cfg["ML_WEIGHT"]
            edge_ats *= cfg["ATS_WEIGHT"]
            edge_ou *= cfg["OU_WEIGHT"]

            scores={"ML":edge_ml,"ATS":edge_ats,"OU":edge_ou}
            best_type=max(scores,key=scores.get)
            best_edge=scores[best_type]
            best_pick={"ML":pick_ml,"ATS":pick_ats,"OU":pick_ou}.get(best_type,pick_ml)
            conf_final=conf_ml if best_type=="ML" else 60+best_edge
            reason=("NFL blended + Adaptive SmartPick" if blended_used else "Adaptive SmartPick")
            lock="🔒" if best_edge>=LOCK_EDGE and conf_final>=LOCK_CONF else ""
            upset="💥" if best_edge>=UPSET_EDGE and conf_final<50 else ""

            row={
                "Sport":sport.split("_")[-1].upper(),
                "GameTime":ev.get("commence_time",""),
                "BestPick":f"{best_pick} ({best_type})",
                "Confidence":round(conf_final,2),
                "Edge":round(best_edge,3),
                "ML":ml_text,"ATS":ats_text,"OU":ou_text,
                "Reason":reason,"LockEmoji":lock,"UpsetEmoji":upset
            }
            rows.append(row)

            append_history([{
                "id":ev.get("id") or str(uuid.uuid4()),
                "sport":sport,"commence_time":ev.get("commence_time",""),
                "team1":t1,"team2":t2,"pick":best_pick,
                "pred_prob":max(p1n,p2n),"edge":best_edge,
                "ml":ml_text,"ats":ats_text,"ou":ou_text,
                "reason":reason,"created_at":datetime.now(timezone.utc).isoformat(),
                "settled":False,"result":""
            }])
        except Exception as e:
            print("⚠️ Event error:", e)
            continue

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
    print("🚀 Done — adaptive model ready for web display.")
