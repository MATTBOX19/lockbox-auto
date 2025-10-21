import os
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
  body { background:#0d1117; color:#c9d1d9; font-family:Inter,Arial,sans-serif; margin:0; padding:1rem;}
  h1 {color:#58a6ff; text-align:center;}
  .update {text-align:center; color:#8b949e; margin-bottom:1rem;}
  select {background:#161b22; color:#c9d1d9; border:1px solid #30363d; border-radius:6px; padding:6px; margin:4px;}
  .grid {display:grid; grid-template-columns:repeat(auto-fit,minmax(320px,1fr)); gap:1rem;}
  .card {background:#161b22; border:1px solid #30363d; border-radius:10px; padding:1rem;}
  .sport-tag {float:right; background:#0d419d; color:white; padding:3px 8px; border-radius:8px; font-size:0.8rem;}
  .team-pick {color:#f1c40f; font-weight:600;}
  .meta {color:#8b949e; font-size:0.9rem;}
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
  </div>

  <div class="grid" id="cards">
    {% for row in rows %}
    <div class="card" data-sport="{{ row.sport_display }}">
      <div><strong>{{ row.matchup }}</strong>
        <span class="sport-tag">{{ row.sport_display }}</span>
      </div>
      <div class="meta">{{ row.gametime }}</div>
      <div class="team-pick">
        {{ row.pick_display }}
        {% if row.lock %}🔒{% endif %}
        {% if row.upset %}🚨{% endif %}
      </div>
      <div class="meta">
        Confidence: {{ row.confidence }} % &nbsp;|&nbsp;
        Edge: {{ row.edge }} %
      </div>
      <div class="meta">
        ML: {{ row.ml }} | ATS: {{ row.ats }} | O/U: {{ row.ou }}
      </div>
      <div class="meta">{{ row.reason }}</div>
    </div>
    {% endfor %}
  </div>

<script>
function filterCards(){
  const sport=document.getElementById('sportFilter').value;
  document.querySelectorAll('.card').forEach(c=>{
    if(sport==="All"||c.dataset.sport===sport){c.style.display="block";}
    else{c.style.display="none";}
  });
}
</script>
</body>
</html>
"""

def normalize_sport(s):
    s = str(s).lower()
    if "nfl" in s: return "NFL"
    if "ncaaf" in s or "cfb" in s or "college" in s: return "NCAA Football"
    if "nba" in s: return "NBA"
    if "mlb" in s: return "MLB"
    if "nhl" in s: return "NHL"
    return s.upper()

@app.route("/")
def index():
    csv_files = [f for f in os.listdir("Output") if f.endswith(".csv")]
    if not csv_files:
        return "No prediction files found."
    latest = sorted(csv_files)[-1]
    df = pd.read_csv(os.path.join("Output", latest))

    rows = []
    for _, row in df.iterrows():
        sport_display = normalize_sport(row.get("Sport",""))
        conf_str = str(row.get("Confidence(%)","0")).replace("%","").strip()
        edge_str = str(row.get("Edge","0")).replace("%","").strip()
        try:
            conf_v = float(conf_str)
        except: conf_v = 0.0
        try:
            edge_v = float(edge_str)
        except: edge_v = 0.0

        pick = str(row.get("MoneylinePick","N/A"))
        reason = str(row.get("Reason","")).strip()
        if not reason: reason = "Model vs Market probability differential"

        # Logic for emojis
        lock = edge_v >= 4.0 or conf_v >= 102.0
        upset = ("underdog" in reason.lower()) or (conf_v < 100 and edge_v >= 2.5)

        rows.append({
            "sport_display": sport_display,
            "matchup": f"{row.get('Team1','')} vs {row.get('Team2','')}",
            "gametime": row.get("GameTime",""),
            "pick_display": pick if pick and pick!='N/A' else "—",
            "confidence": f"{conf_v:.1f}",
            "edge": f"{edge_v:.1f}",
            "ml": pick if pick and pick!='N/A' else "—",
            "ats": "—",
            "ou": "—",
            "reason": reason,
            "lock": lock,
            "upset": upset
        })

    return render_template_string(TEMPLATE, rows=rows, updated=latest.replace("Predictions_","").replace("_Explained.csv",""))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
