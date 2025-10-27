#!/usr/bin/env python3
"""
LockBox Pro Web — Learning Dashboard Edition
Displays live picks + historical performance from history.csv
"""
from flask import Flask, render_template_string, jsonify, request
import pandas as pd, os, glob, re
from collections import defaultdict
from datetime import datetime

app = Flask(__name__)

# === Config ===
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "/opt/render/project/src/Output")
FALLBACK_FILE = os.path.join(OUTPUT_DIR, "Predictions_test.csv")
LATEST_NAME = "Predictions_latest_Explained.csv"

def log(msg): print(msg, flush=True)

# === Performance Utility ===
def compute_sport_performance():
    """Read Output/history.csv and summarize win/loss % by sport."""
    path = os.path.join(OUTPUT_DIR, "history.csv")
    if not os.path.exists(path): return []
    try:
        df = pd.read_csv(path)
    except Exception:
        return []
    if df.empty: return []

    recent = df.tail(250)
    perf = defaultdict(lambda: {"W":0,"L":0})
    for _,r in recent.iterrows():
        sport=str(r.get("Sport","")).upper()
        res=str(r.get("Result","")).upper()
        if sport and res in ["WIN","LOSS"]:
            if res=="WIN": perf[sport]["W"]+=1
            else: perf[sport]["L"]+=1

    data=[]
    for s,v in perf.items():
        total=v["W"]+v["L"]
        if total==0: continue
        pct=round(100*v["W"]/total,1)
        data.append({"sport":s,"wins":v["W"],"losses":v["L"],"pct":pct})
    data.sort(key=lambda x:-x["pct"])
    return data

def perf_html():
    data=compute_sport_performance()
    if not data: return "No performance data yet."
    html=["<div style='display:flex;flex-wrap:wrap;justify-content:center;gap:10px;'>"]
    emoji={"NFL":"🏈","CFB":"🎓","NBA":"🏀","MLB":"⚾","NHL":"🏒"}
    for row in data:
        e=emoji.get(row["sport"],"🎯")
        bar=f"<div style='width:{row['pct']}%;background:#238636;height:6px;border-radius:3px;'></div>"
        html.append(
            f"<div style='padding:6px 10px;background:#161b22;border:1px solid #30363d;border-radius:8px;text-align:center;min-width:100px;'>"
            f"<b>{e} {row['sport']}</b><br>"
            f"<small>{row['wins']}-{row['losses']} ({row['pct']}%)</small>"
            f"{bar}</div>"
        )
    html.append("</div>")
    return "".join(html)

# === Prediction Utils ===
def find_latest_file():
    latest=os.path.join(OUTPUT_DIR,LATEST_NAME)
    if os.path.exists(latest): return latest
    files=glob.glob(os.path.join(OUTPUT_DIR,"Predictions_*_Explained.csv"))
    if files:
        files.sort(key=os.path.getmtime,reverse=True)
        return files[0]
    if os.path.exists(FALLBACK_FILE): return FALLBACK_FILE
    return None

def parse_teams_from_ml(val):
    try:
        parts=str(val).split("|")
        if len(parts)>=2:
            t1=parts[0].split(":")[0].strip()
            t2=parts[1].split(":")[0].strip()
            return t1,t2
    except: pass
    return None,None

def load_predictions():
    path=find_latest_file()
    if not path: return pd.DataFrame(), "NO_FILE"
    try: df=pd.read_csv(path)
    except Exception as e:
        log(f"⚠️ could not read {path}: {e}")
        return pd.DataFrame(), "READ_ERROR"

    df.columns=[c.strip() for c in df.columns]
    if "Confidence(%)" in df.columns and "Confidence" not in df.columns:
        df.rename(columns={"Confidence(%)":"Confidence"},inplace=True)
    if "MoneylinePick" not in df.columns and "BestPick" in df.columns:
        df["MoneylinePick"]=df["BestPick"]

    # fill missing team names
    if "Team1" not in df.columns: df["Team1"]=""
    if "Team2" not in df.columns: df["Team2"]=""
    if "ML" in df.columns:
        mask=(df["Team1"].str.strip()=="")|(df["Team2"].str.strip()=="")
        for i in df[mask].index:
            t1,t2=parse_teams_from_ml(df.at[i,"ML"])
            df.at[i,"Team1"]=t1 or ""
            df.at[i,"Team2"]=t2 or ""

    df["Edge"]=pd.to_numeric(df.get("Edge",0),errors="coerce").fillna(0.0)
    df["Confidence"]=pd.to_numeric(df.get("Confidence",0),errors="coerce").fillna(0.0)
    df["EdgeDisplay"]=df["Edge"].round(3).astype(str)

    df["LockEmoji"]=df.get("LockEmoji","")
    df["UpsetEmoji"]=df.get("UpsetEmoji","")
    df["Sport_raw"]=df.get("Sport","").astype(str)
    df["Sport"]=df["Sport_raw"].replace({
        "americanfootball_nfl":"NFL","americanfootball_ncaaf":"CFB",
        "basketball_nba":"NBA","baseball_mlb":"MLB","icehockey_nhl":"NHL"})
    return df,os.path.basename(path)

# === Template ===
TEMPLATE = """
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>🔥 LockBox AI Picks 🔒</title>
<style>
body{background:#0d1117;color:#c9d1d9;font-family:system-ui,Segoe UI,Roboto,Arial;margin:0;padding:0;}
h1{color:#58a6ff;text-align:center;padding:20px 0;margin:0;}
.updated{text-align:center;font-size:.9rem;color:#8b949e;margin-top:-10px}
.filters{display:flex;justify-content:center;margin:15px;gap:10px;flex-wrap:wrap}
select{background:#161b22;color:#c9d1d9;border:1px solid #30363d;padding:6px 10px;border-radius:6px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));max-width:1400px;margin:0 auto 40px;gap:14px;padding:0 20px}
.card{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:16px}
.game-title{color:#58a6ff;font-weight:700;margin-bottom:6px;font-size:1rem}
.pick{color:#e3b341;font-weight:700;margin:4px 0}
.meta{font-size:.9rem;color:#8b949e}
.lock{color:#f0c420;margin-left:4px}
.upset{color:#f85149;margin-left:4px}
.perfbar{text-align:center;background:#161b22;color:#79c0ff;font-size:1rem;padding:10px 0;border-bottom:1px solid #30363d}
.footer{max-width:1400px;margin:0 auto 30px;color:#8b949e;font-size:.9rem;padding:10px 20px;text-align:center}
</style>
</head>
<body>
<div class="perfbar">{{ perf_html|safe }}</div>
<h1>🔥 LockBox AI Picks 🔒</h1>
<div class="updated">Updated: {{ updated }}</div>

<div class="filters">
  <label>Sport</label>
  <select id="sport" onchange="updateFilters()">
    <option value="All">All</option>
    {% for s in sports %}
      <option value="{{s}}" {% if s==sport %}selected{% endif %}>{{s}}</option>
    {% endfor %}
  </select>
  <label>Top 5</label>
  <select id="top5" onchange="updateFilters()">
    <option value="All" {% if top5=='All' %}selected{% endif %}>All</option>
    <option value="1" {% if top5=='1' %}selected{% endif %}>Top 5</option>
  </select>
</div>

<div class="grid">
{% for row in data %}
  <div class="card">
    <div class="game-title">
      {{ row.Team1 }} vs {{ row.Team2 }}
      <span style="float:right;color:#79c0ff;">{{ row.Sport }}</span>
      {% if row.LockEmoji %}<span class="lock">{{ row.LockEmoji }}</span>{% endif %}
      {% if row.UpsetEmoji %}<span class="upset">{{ row.UpsetEmoji }}</span>{% endif %}
    </div>
    <div class="meta">{{ row.GameTime }}</div>
    <div class="pick">{{ row.MoneylinePick }}</div>
    <div class="meta">
      Confidence: {{ "%.1f"|format(row.Confidence) }}% | Edge: {{ row.EdgeDisplay }}<br>
      ML: {{ row.ML }} | ATS: {{ row.ATS }} | O/U: {{ row.OU }}<br>
      {{ row.Reason }}
    </div>
  </div>
{% endfor %}
</div>

<div class="footer">{{ footer_text }}</div>

<script>
function updateFilters(){
  const s=document.getElementById("sport").value;
  const t=document.getElementById("top5").value;
  window.location.href=`/?sport=${s}&top5=${t}`;
}
</script>
</body></html>
"""

# === Routes ===
@app.route("/")
def index():
    sport=request.args.get("sport","All")
    top5=request.args.get("top5","All")

    df,filename=load_predictions()
    sports=sorted(df["Sport"].dropna().unique()) if not df.empty else []

    if not df.empty:
        if sport!="All": df=df[df["Sport"]==sport]
        if top5=="1":
            df["Score"]=df["Edge"]*df["Confidence"]
            df=df.sort_values("Score",ascending=False).head(5)

    footer=f"Showing {len(df)} picks from {filename}"
    return render_template_string(
        TEMPLATE,
        data=df.to_dict(orient="records"),
        updated=filename,
        sports=sports,
        sport=sport,
        top5=top5,
        footer_text=footer,
        perf_html=perf_html(),
    )

@app.route("/api/status")
def api_status():
    df,filename=load_predictions()
    return jsonify({
        "status":"ok",
        "records":len(df),
        "file":filename,
        "last_updated":datetime.utcnow().isoformat()+"Z",
        "performance":compute_sport_performance()
    })

@app.route("/api/picks")
def api_picks():
    df,filename=load_predictions()
    if df.empty:
        return jsonify({"message":"no picks yet","records":0,"file":filename})
    return jsonify({"records":len(df),"file":filename,"picks":df.to_dict(orient="records")})

if __name__=="__main__":
    app.run(host="0.0.0.0",port=10000)
