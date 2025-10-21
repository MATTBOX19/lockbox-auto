import os
import time
import pandas as pd
from flask import Flask, render_template_string

app = Flask(__name__)

TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>🔥 LockBox AI Picks 🔒</title>
<style>
body{background:#0d1117;color:#c9d1d9;font-family:Inter,Arial,sans-serif;margin:0;padding:1rem;}
h1{color:#58a6ff;text-align:center;}
.update{text-align:center;color:#8b949e;margin-bottom:1rem;}
select{background:#161b22;color:#c9d1d9;border:1px solid #30363d;border-radius:6px;padding:6px;margin:4px;}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:1rem;}
.card{background:#161b22;border:1px solid #30363d;border-radius:10px;padding:1rem;}
.sport-tag{float:right;background:#0d419d;color:white;padding:3px 8px;border-radius:8px;font-size:0.8rem;}
.team-pick{color:#f1c40f;font-weight:600;}
.meta{color:#8b949e;font-size:0.9rem;}
</style>
</head>
<body>
<h1>🔥 LockBox AI Picks 🔒</h1>
<div class="update">Your edge, every game — Updated: {{ updated }}</div>

<div style="text-align:center;">
  Sport:
  <select id="sportFilter" onchange="filterCards()">
    <option value="All">All</option>
    <option value="NFL">NFL</option>
    <option value="NCAA Football">NCAA Football</option>
    <option value="NBA">NBA</option>
    <option value="MLB">MLB</option>
    <option value="NHL">NHL</option>
  </select>
  &nbsp;&nbsp;Top 5:
  <select id="topFilter" onchange="filterCards()">
    <option value="All">All</option>
    <option value="Top5">Top 5</option>
  </select>
</div>

<div class="grid" id="cards">
{% for row in rows %}
  <div class="card" data-sport="{{ row.sport_display }}">
    <div><strong>{{ row.matchup }}</strong><span class="sport-tag">{{ row.sport_display }}</span></div>
    <div class="meta">{{ row.gametime }}</div>
    <div class="team-pick">
      {{ row.pick_display }}
      {% if row.lock %}🔒{% endif %}
      {% if row.upset %}🚨{% endif %}
    </div>
    <div class="meta">Confidence: {{ row.confidence }} % | Edge: {{ row.edge }} %</div>
    <div class="meta">ML: {{ row.ml }} | ATS: {{ row.ats }} | O/U: {{ row.ou }}</div>
    <div class="meta">{{ row.reason }}</div>
  </div>
{% endfor %}
</div>

<script>
function filterCards(){
  const sport=document.getElementById('sportFilter').value;
  const top=document.getElementById('topFilter').value;
  const cards=[...document.querySelectorAll('.card')];
  cards.forEach((c,i)=>{
    const matchSport=(sport==="All"||c.dataset.sport===sport);
    const matchTop=(top==="All"||(i<5));
    c.style.display=(matchSport&&matchTop)?"block":"none";
  });
}
</script>
</body>
</html>
"""

def normalize_sport(s):
    s=str(s).lower()
    if "nfl" in s: return "NFL"
    if "ncaaf" in s or "college" in s or "cfb" in s: return "NCAA Football"
    if "nba" in s: return "NBA"
    if "mlb" in s: return "MLB"
    if "nhl" in s: return "NHL"
    return s.upper()

@app.route("/")
def index():
    # wait for valid CSV (guard)
    for _ in range(10):
        csv_files=[f for f in os.listdir("Output") if f.endswith(".csv") and "Predictions_" in f]
        if csv_files: break
        time.sleep(1)
    if not csv_files:
        return "No prediction file found yet. Try again shortly."
    latest=sorted(csv_files)[-1]
    path=os.path.join("Output",latest)
    if os.path.getsize(path)<100:  # guard for empty test.csv
        time.sleep(2)
    df=pd.read_csv(path)
    if df.empty:
        return "Waiting for predictions to populate..."

    rows=[]
    for _,r in df.iterrows():
        sport_display=normalize_sport(r.get("Sport",""))
        try: conf=float(str(r.get("Confidence(%)","0")).replace("%",""))
        except: conf=0
        try: edge=float(str(r.get("Edge","0")).replace("%",""))
        except: edge=0
        pick=str(r.get("MoneylinePick","—"))
        reason=str(r.get("Reason","Model vs Market probability differential")).strip()
        lock=edge>=4 or conf>=102
        upset=("underdog" in reason.lower()) or (conf<100 and edge>=2.5)
        rows.append({
          "sport_display":sport_display,
          "matchup":f"{r.get('Team1','')} vs {r.get('Team2','')}",
          "gametime":r.get("GameTime",""),
          "pick_display":pick,
          "confidence":f"{conf:.1f}",
          "edge":f"{edge:.1f}",
          "ml":pick,
          "ats":"—",
          "ou":"—",
          "reason":reason,
          "lock":lock,
          "upset":upset
        })

    return render_template_string(TEMPLATE,rows=rows,
           updated=latest.replace("Predictions_","").replace("_Explained.csv",""))

if __name__=="__main__":
    app.run(host="0.0.0.0",port=5000)
