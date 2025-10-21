# lockbox_web.py – Edit 6
from flask import Flask, request, render_template_string
import pandas as pd, glob, os, datetime, re

app = Flask(__name__)

# ---------- HTML ----------
TEMPLATE = """<!doctype html>
<html><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>LockBox AI Picks</title>
<style>
:root{--bg:#0b0f12;--card:#0f1920;--muted:#9aa6b2;--accent:#29a3ff;--gold:#d4a10a;--pill:#091619;--text:#dbe7ef;}
body{background:var(--bg);color:var(--text);font-family:Inter,system-ui,Segoe UI,Roboto,Arial;margin:0}
.wrap{max-width:1200px;margin:28px auto;padding:20px}
header{display:flex;flex-wrap:wrap;justify-content:space-between;align-items:center;gap:12px}
h1{margin:0;font-size:28px;color:var(--accent)}
.subtitle{color:var(--muted);font-size:14px;margin-top:6px}
select{background:var(--pill);border:1px solid rgba(255,255,255,0.05);color:var(--text);padding:10px;border-radius:8px}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:18px;margin-top:22px}
.card{background:linear-gradient(180deg,rgba(255,255,255,0.02),rgba(255,255,255,0));border:1px solid rgba(255,255,255,0.05);
padding:18px;border-radius:12px;box-shadow:0 4px 16px rgba(0,0,0,.6)}
.pick{margin-top:14px;font-weight:700;color:var(--gold);font-size:16px}
.lock{margin-left:6px} .siren{color:#ff5c5c;margin-left:6px}
.small{font-size:13px;color:var(--muted)}
.sport-pill{background:#062128;color:var(--accent);padding:4px 7px;border-radius:6px;font-weight:600;font-size:12px}
.no-data{color:var(--muted);padding:40px;text-align:center}
@media(max-width:620px){.cards{grid-template-columns:1fr}}
</style></head>
<body><div class="wrap">
<header>
  <div><h1>🔥 LockBox AI Picks 🔒</h1>
  <div class="subtitle">Your edge, every game — Updated: {{updated_at}}</div></div>
  <div>
    <label>Sport </label>
    <select id="sport" onchange="applyFilter()">
      <option value="All" {%if selected_sport=='All'%}selected{%endif%}>All</option>
      {%for opt in sport_options%}
        <option value="{{opt}}" {%if opt==selected_sport%}selected{%endif%}>{{opt}}</option>
      {%endfor%}
    </select>
    <label style="margin-left:10px">Top 5 </label>
    <select id="top5" onchange="applyFilter()">
      <option value="0" {%if not top5%}selected{%endif%}>All</option>
      <option value="1" {%if top5%}selected{%endif%}>Top 5</option>
    </select>
  </div>
</header>

{%if not rows%}
<div class="no-data">No predictions found in Output/ folder.</div>
{%else%}
<div style="margin-top:18px;font-size:13px;color:var(--muted)">{{rows|length}} picks shown</div>
<div class="cards">
{%for r in rows%}
  <div class="card">
    <div style="display:flex;justify-content:space-between;align-items:flex-start">
      <div><h3 style="margin:0;color:#6ed0ff;font-size:16px">{{r.title}}</h3>
      <div class="small">{{r.gametime}}</div></div>
      <div style="text-align:right">
        <div class="sport-pill">{{r.sport}}</div>
        <div style="margin-top:6px;font-weight:700">{{r.edge}}</div>
      </div>
    </div>
    <div class="pick">{{r.pick}}
      {%if r.lock%}<span class="lock">🔒</span>{%endif%}
      {%if r.upset%}<span class="siren">🚨</span>{%endif%}
    </div>
    <div class="small" style="margin-top:8px">
      Confidence: {{r.confidence}} | Edge: {{r.edge}}
    </div>
    <div class="small" style="margin-top:6px">
      ML: {{r.ml}} | ATS: {{r.ats}} | O/U: {{r.ou}}
    </div>
    <div class="small" style="margin-top:6px">{{r.reason}}</div>
  </div>
{%endfor%}
</div>{%endif%}
</div>
<script>
function applyFilter(){
  const s=document.getElementById('sport').value;
  const t=document.getElementById('top5').value;
  const q=new URLSearchParams(window.location.search);
  q.set('sport',s);q.set('top5',t);
  window.location.search=q.toString();
}
</script></body></html>"""

# ---------- helpers ----------
def find_latest_csv():
    cands=sorted(glob.glob("Output/*.csv")+glob.glob("*.csv"),key=os.path.getmtime,reverse=True)
    return cands[0] if cands else None

def find_col(df,names):
    cols={c.lower():c for c in df.columns}
    for n in names:
        if not n:continue
        n=n.lower()
        if n in cols:return cols[n]
    for n in names:
        if not n:continue
        for c in df.columns:
            if n in c.lower():return c
    return None

def parse_num(v):
    if v is None or (isinstance(v,float) and pd.isna(v)):return None
    s=str(v).strip().replace('%','')
    try:return float(s)
    except:return None

def parse_ml(v):
    if v is None:return None
    m=re.search(r'([+-]?\d+)',str(v))
    return int(m.group(1)) if m else None

def norm_sport(s):
    if not s:return "Unknown"
    s=re.sub(r'[^a-z]','',str(s).lower())
    if 'ncaaf' in s or 'collegefootball' in s or 'ncaa' in s:return 'NCAA Football'
    if 'nfl' in s:return 'NFL'
    if 'nba' in s or 'basketball' in s:return 'NBA'
    if 'mlb' in s or 'baseball' in s:return 'MLB'
    if 'nhl' in s or 'hockey' in s:return 'NHL'
    return s.upper()

# ---------- main ----------
@app.route("/")
def index():
    path=find_latest_csv()
    if not path:
        return render_template_string(TEMPLATE,rows=[],sport_options=[],selected_sport='All',top5=False,updated_at='No data')
    try:df=pd.read_csv(path)
    except Exception as e:return f"Error reading CSV: {e}",500

    sport_col=find_col(df,['sport','league'])
    t1=find_col(df,['team1','home','home_team'])
    t2=find_col(df,['team2','away','away_team'])
    pick=find_col(df,['pick','moneylinepick','predicted_winner'])
    conf=find_col(df,['confidence','confidence(%)'])
    edge=find_col(df,['edge'])
    ml=find_col(df,['ml','moneyline'])
    ats=find_col(df,['ats','spread'])
    ou=find_col(df,['ou','overunder','total'])
    reason=find_col(df,['reason','explanation'])

    rows=[]
    for _,r in df.iterrows():
        conf_v=parse_num(r[conf]) if conf else 100
        edge_v=parse_num(r[edge]) if edge else 0
        ml_v=parse_ml(r[ml]) if ml else None
        lock=(edge_v>=3 or conf_v>=101)
        upset=(ml_v and ml_v>120)
        rows.append(dict(
            sport=norm_sport(r[sport_col]) if sport_col else "Unknown",
            title=f"{r[t1]} vs {r[t2]}" if t1 and t2 else "",
            gametime=r.get('gametime',''),
            pick=str(r[pick]) if pick and pd.notna(r[pick]) else "N/A",
            confidence=f"{round(conf_v,1)}%" if conf_v else "N/A",
            edge=f"{round(edge_v,1)}%",
            ml=r[ml] if ml else "N/A",
            ats=r[ats] if ats else "N/A",
            ou=r[ou] if ou else "N/A",
            reason=r[reason] if reason else "Model vs Market probability differential",
            lock=lock,upset=upset,score=edge_v*(conf_v-100)
        ))

    # sports order
    sports=sorted({r["sport"] for r in rows})
    pref=['NFL','NCAA Football','NBA','MLB','NHL']
    sport_opts=[p for p in pref if p in sports]+[s for s in sports if s not in pref]

    sel=request.args.get('sport','All')
    top5=request.args.get('top5','0') in ('1','true','True')
    f=[r for r in rows if sel in ('All','') or r['sport']==sel]

    # sort & top5 per sport
    if top5:
        out=[]
        for sp in {r['sport'] for r in f}:
            picks=[r for r in f if r['sport']==sp]
            picks=sorted(picks,key=lambda x:x['score'],reverse=True)[:5]
            out+=picks
        f=out
    else:
        f=sorted(f,key=lambda x:x['score'],reverse=True)

    mt=os.path.getmtime(path)
    upd=datetime.datetime.utcfromtimestamp(mt).strftime("%Y-%m-%d %H:%M UTC")
    return render_template_string(TEMPLATE,rows=f,sport_options=sport_opts,selected_sport=sel,top5=top5,updated_at=upd)

if __name__=="__main__":
    app.run(host="0.0.0.0",port=int(os.environ.get("PORT",10000)),debug=False)
