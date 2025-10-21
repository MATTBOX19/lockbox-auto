# lockbox_web.py
# Flask web app for LockBox AI Picks
# Includes: dropdown by sport, Top 5 filter, auto-lock/upset icons, ML/ATS/O/U, confidence %, edge %, dark theme

from flask import Flask, request, render_template_string
import pandas as pd
import glob
import os
import datetime

app = Flask(__name__)

TEMPLATE = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>🔥 LockBox AI Picks 🔒</title>
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <style>
    :root {
      --bg:#0b0f12;
      --card:#0f1920;
      --muted:#9aa6b2;
      --accent:#29a3ff;
      --gold:#d4a10a;
      --pill:#091619;
      --text:#dbe7ef;
    }
    body { background:var(--bg); color:var(--text); font-family:Inter,system-ui,Segoe UI,Roboto,Arial; margin:0; padding:0; }
    .wrap { max-width:1200px; margin:30px auto; padding:16px; }
    header { display:flex; justify-content:space-between; flex-wrap:wrap; align-items:center; }
    h1 { margin:0; font-size:28px; color:var(--accent); }
    .subtitle { color:var(--muted); font-size:14px; margin-top:6px; }
    .controls { display:flex; gap:10px; align-items:center; }
    select { background:var(--pill); color:var(--text); border:1px solid rgba(255,255,255,0.1); border-radius:8px; padding:8px 10px; }
    .cards { display:grid; grid-template-columns:repeat(auto-fill,minmax(300px,1fr)); gap:18px; margin-top:20px; }
    .card { background:var(--card); border-radius:12px; padding:18px; border:1px solid rgba(255,255,255,0.05); box-shadow:0 4px 12px rgba(0,0,0,0.6); }
    .pick { color:var(--gold); font-weight:700; margin-top:10px; font-size:16px; }
    .meta { font-size:13px; color:var(--muted); margin-top:4px; }
    .sport-pill { background:#062128; color:var(--accent); padding:4px 8px; border-radius:8px; font-size:12px; }
    .row { display:flex; justify-content:space-between; align-items:center; margin-top:10px; font-size:13px; color:var(--muted); }
    .small { font-size:13px; color:var(--muted); }
    .lock { margin-left:6px; }
    .siren { color:#ff5c5c; margin-left:6px; }
    .no-data { text-align:center; color:var(--muted); margin-top:50px; }
    @media (max-width:620px){ .cards{ grid-template-columns:1fr; } }
  </style>
</head>
<body>
  <div class="wrap">
    <header>
      <div>
        <h1>🔥 LockBox AI Picks 🔒</h1>
        <div class="subtitle">Your edge, every game — Updated: {{ updated_at }}</div>
      </div>
      <div class="controls">
        <div>
          <label for="sport">Sport</label><br>
          <select id="sport" onchange="applyFilter()">
            <option value="All" {% if selected_sport=='All' %}selected{% endif %}>All</option>
            {% for opt in sport_options %}
              <option value="{{ opt }}" {% if opt==selected_sport %}selected{% endif %}>{{ opt }}</option>
            {% endfor %}
          </select>
        </div>
        <div>
          <label for="top5">Top 5</label><br>
          <select id="top5" onchange="applyFilter()">
            <option value="0" {% if not top5 %}selected{% endif %}>All</option>
            <option value="1" {% if top5 %}selected{% endif %}>Top 5</option>
          </select>
        </div>
      </div>
    </header>

    {% if not rows %}
      <div class="no-data">No predictions found</div>
    {% else %}
      <div style="margin-top:12px;font-size:13px;color:var(--muted)">{{ rows|length }} picks shown</div>
      <div class="cards">
        {% for r in rows %}
        <div class="card">
          <div style="display:flex;justify-content:space-between;align-items:flex-start">
            <div style="flex:1">
              <h3 style="margin:0;color:#6ed0ff;font-size:16px">{{ r.title }}</h3>
              <div class="meta">{{ r.gametime }}</div>
            </div>
            <div style="text-align:right">
              <div class="sport-pill">{{ r.sport }}</div>
              <div style="margin-top:6px">{{ r.edge }}</div>
            </div>
          </div>
          <div class="pick">{{ r.pick }}
            {% if r.lock %}<span class="lock">🔒</span>{% endif %}
            {% if r.upset %}<span class="siren">🚨</span>{% endif %}
          </div>
          <div class="small" style="margin-top:6px">
            Confidence: <strong>{{ r.confidence }}</strong> | Edge: <strong>{{ r.edge }}</strong>
          </div>
          <div class="row">
            <div>ML: <strong>{{ r.ml }}</strong></div>
            <div>ATS: <strong>{{ r.ats }}</strong></div>
            <div>O/U: <strong>{{ r.ou }}</strong></div>
          </div>
          <div class="meta" style="margin-top:8px">{{ r.reason }}</div>
        </div>
        {% endfor %}
      </div>
    {% endif %}
  </div>

<script>
function applyFilter(){
  const sport = document.getElementById('sport').value;
  const top5 = document.getElementById('top5').value;
  const qs = new URLSearchParams(window.location.search);
  qs.set('sport', sport);
  qs.set('top5', top5);
  window.location.search = qs.toString();
}
</script>
</body>
</html>
"""

def latest_csv():
    paths = glob.glob("Output/Predictions_*.csv") + glob.glob("Output/*.csv")
    if not paths: return None
    paths.sort(key=lambda x: os.path.getmtime(x), reverse=True)
    return paths[0]

@app.route("/")
def index():
    csv_path = latest_csv()
    if not csv_path:
        return render_template_string(TEMPLATE, rows=[], sport_options=[], selected_sport="All", top5=False, updated_at="N/A")

    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        return f"Error reading CSV: {e}", 500

    # Normalize sport codes
    sport_map = {
        "americanfootball_nfl": "NFL",
        "americanfootball_ncaaf": "NCAA",
        "basketball_nba": "NBA",
        "baseball_mlb": "MLB",
        "icehockey_nhl": "NHL"
    }

    rows = []
    for _, row in df.iterrows():
        sport = sport_map.get(str(row.get("Sport","")).strip(), row.get("Sport","Unknown"))
        pick = str(row.get("Pick","N/A"))
        confidence = float(row.get("Confidence(%)", row.get("Confidence", 0)))
        edge = float(row.get("Edge", 0))

        lock = confidence >= 105 or edge >= 4.0
        upset = str(row.get("PickOdds","")).startswith("+")  # mark underdog as upset

        rows.append({
            "sport": sport,
            "title": f"{row.get('Team1','')} vs {row.get('Team2','')}",
            "gametime": row.get("GameTime",""),
            "pick": pick,
            "confidence": f"{confidence:.1f}%",
            "edge": f"{edge:.1f}%",
            "lock": lock,
            "upset": upset,
            "ml": row.get("ML","N/A"),
            "ats": row.get("ATS","N/A"),
            "ou": row.get("OU","N/A"),
            "reason": row.get("Reason","Model vs Market probability differential")
        })

    selected_sport = request.args.get("sport","All")
    top5 = request.args.get("top5","0") in ["1","true","True"]

    if selected_sport != "All":
        rows = [r for r in rows if r["sport"] == selected_sport]

    rows.sort(key=lambda x: float(x["edge"].replace("%","")), reverse=True)
    if top5: rows = rows[:5]

    updated_at = datetime.datetime.utcfromtimestamp(os.path.getmtime(csv_path)).strftime("%Y-%m-%d %H:%M UTC")

    sport_options = sorted(set(r["sport"] for r in rows if r["sport"]))

    return render_template_string(TEMPLATE, rows=rows, sport_options=sport_options,
                                  selected_sport=selected_sport, top5=top5, updated_at=updated_at)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)), debug=False)
