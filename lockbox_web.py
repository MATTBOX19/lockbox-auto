# lockbox_web.py — FINAL
# Flask web interface for LockBox AI picks

from flask import Flask, request, render_template_string
import pandas as pd
import glob, os, datetime

app = Flask(__name__)

# HTML Template
TEMPLATE = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>LockBox AI Picks</title>
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <style>
    body{margin:0;background:#0b0f12;color:#dbe7ef;font-family:Inter,system-ui,Segoe UI,Roboto,Arial}
    .wrap{max-width:1200px;margin:28px auto;padding:20px}
    header{display:flex;gap:12px;align-items:center;flex-wrap:wrap;justify-content:space-between}
    h1{margin:0;font-size:28px;color:#29a3ff}
    .subtitle{color:#9aa6b2;font-size:14px;margin-top:6px}
    select{background:#091619;border:1px solid rgba(255,255,255,0.05);color:#dbe7ef;padding:10px;border-radius:8px;font-size:14px}
    .cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:18px;margin-top:22px}
    .card{background:#0f1920;border-radius:12px;padding:18px;border:1px solid rgba(255,255,255,0.05);box-shadow:0 4px 18px rgba(0,0,0,0.6)}
    .card h3{margin:0;color:#6ed0ff;font-size:16px}
    .meta{font-size:12px;color:#9aa6b2;margin-top:8px}
    .pick{margin-top:14px;font-weight:700;color:#d4a10a;font-size:16px}
    .small{font-size:13px;color:#9aa6b2}
    .sport-pill{background:#062128;color:#29a3ff;padding:6px 8px;border-radius:8px;font-weight:600;font-size:12px}
    .no-data{color:#9aa6b2;padding:40px;text-align:center}
  </style>
</head>
<body>
<div class="wrap">
  <header>
    <div>
      <h1>🔥 LockBox AI Picks 🔒</h1>
      <div class="subtitle">Your edge, every game — Updated: {{ updated_at }}</div>
    </div>
    <div>
      <label>Sport</label>
      <select id="sport" onchange="applyFilter()">
        <option value="All">All</option>
        {% for opt in sport_options %}
          <option value="{{opt}}" {% if opt==selected_sport %}selected{% endif %}>{{opt}}</option>
        {% endfor %}
      </select>
      <label style="margin-left:10px;">Top 5</label>
      <select id="top5" onchange="applyFilter()">
        <option value="0" {% if not top5 %}selected{% endif %}>All</option>
        <option value="1" {% if top5 %}selected{% endif %}>Top 5</option>
      </select>
    </div>
  </header>

  {% if not rows %}
    <div class="no-data">No predictions found. Ensure Output/Predictions_*.csv exists.</div>
  {% else %}
    <div style="margin-top:18px;font-size:13px;color:#9aa6b2">{{rows|length}} picks shown</div>
    <div class="cards">
      {% for r in rows %}
      <div class="card">
        <div style="display:flex;justify-content:space-between;align-items:flex-start">
          <div>
            <h3>{{ r.title }}</h3>
            <div class="meta">{{ r.gametime }}</div>
          </div>
          <div class="sport-pill">{{ r.sport }}</div>
        </div>
        <div class="pick">
          {{ r.pick }}
          {% if r.lock %} 🔒{% endif %}
          {% if r.upset %} 🚨{% endif %}
        </div>
        <div class="small" style="margin-top:8px">
          Confidence: {{ r.confidence }} | Edge: {{ r.edge }}
        </div>
        <div class="small" style="margin-top:6px">
          ML: {{ r.ml }} | ATS: {{ r.ats }} | O/U: {{ r.ou }}
        </div>
        <div class="small" style="margin-top:8px">{{ r.reason }}</div>
      </div>
      {% endfor %}
    </div>
  {% endif %}
</div>

<script>
function applyFilter(){
  const s=document.getElementById('sport').value;
  const t=document.getElementById('top5').value;
  const q=new URLSearchParams(window.location.search);
  q.set('sport',s); q.set('top5',t);
  window.location.search=q.toString();
}
</script>
</body>
</html>
"""

def find_latest_csv():
    files = sorted(glob.glob("Output/*.csv"), key=os.path.getmtime, reverse=True)
    return files[0] if files else None

@app.route("/")
def index():
    csv_path = find_latest_csv()
    if not csv_path:
        return render_template_string(TEMPLATE, rows=[], sport_options=[], selected_sport="All", top5=False, updated_at="No data")

    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        return f"Error reading CSV: {e}", 500

    rows=[]
    for _, row in df.iterrows():
        sport = str(row.get("Sport","")).strip()
        if sport.lower() in ["americanfootball_nfl"]: sport="NFL"
        elif sport.lower() in ["americanfootball_ncaaf","ncaaf","collegefootball"]: sport="NCAA"
        elif sport.lower() in ["basketball_nba"]: sport="NBA"
        elif sport.lower() in ["icehockey_nhl"]: sport="NHL"
        elif sport.lower() in ["baseball_mlb"]: sport="MLB"

        team1=row.get("Team1") or row.get("home_team") or row.get("Home") or ""
        team2=row.get("Team2") or row.get("away_team") or row.get("Away") or ""
        title=f"{team1} vs {team2}".strip()
        pick=row.get("Pick") or row.get("moneylinepick") or row.get("SelectedTeam") or row.get("RecommendedPick") or "N/A"

        conf=row.get("Confidence") or row.get("confidence(%)") or 0
        try: conf=float(str(conf).replace("%","")); conf_str=f"{conf:.1f}%"
        except: conf_str=str(conf)

        edge=row.get("Edge") or row.get("edge") or 0
        try: edge=float(str(edge).replace("%","")); edge_str=f"{edge:.1f}%"
        except: edge_str=str(edge)

        ml=row.get("ML") or row.get("moneyline_home") or row.get("home_ml") or row.get("Moneyline") or "N/A"
        ats=row.get("ATS") or row.get("Spread") or row.get("Line") or "N/A"
        ou=row.get("OU") or row.get("Total") or row.get("OverUnder") or row.get("O/U") or "N/A"

        # Auto logic for lock/upset
        lock=(isinstance(conf,(int,float)) and conf>101.5) and (isinstance(edge,(int,float)) and edge>=3.0)
        upset=False
        try:
            if str(ml).startswith("+") and float(ml.replace("+",""))>=150: upset=True
        except: pass

        rows.append({
            "sport":sport,"title":title,
            "gametime":row.get("GameTime") or row.get("Date") or "",
            "pick":pick,"confidence":conf_str,"edge":edge_str,
            "ml":ml,"ats":ats,"ou":ou,
            "reason":row.get("Reason") or "Model vs Market probability differential",
            "lock":lock,"upset":upset
        })

    # Sports list
    sport_options=sorted({r["sport"] for r in rows if r["sport"]})
    if "NCAA" in sport_options: sport_options.remove("NCAA"); sport_options.insert(1,"NCAA")

    selected=request.args.get("sport","All")
    top5=request.args.get("top5","0")=="1"
    filtered=[r for r in rows if selected=="All" or r["sport"]==selected]
    filtered=sorted(filtered,key=lambda r: float(str(r["edge"]).replace("%","") or 0),reverse=True)
    if top5: filtered=filtered[:5]

    updated=datetime.datetime.utcfromtimestamp(os.path.getmtime(csv_path)).strftime("%Y-%m-%d %H:%M UTC")
    return render_template_string(TEMPLATE,rows=filtered,sport_options=sport_options,selected_sport=selected,top5=top5,updated_at=updated)

if __name__=="__main__":
    app.run(host="0.0.0.0",port=int(os.environ.get("PORT",10000)),debug=False)
