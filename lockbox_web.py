from flask import Flask, render_template_string, request
import pandas as pd
import os

app = Flask(__name__)

# === CONFIG ===
OUTPUT_DIR = "/opt/render/project/src/Output"
PRIMARY_FILE = "Predictions_2025-10-21_Explained.csv"
FALLBACK_FILE = "Predictions_test.csv"

# === HTML TEMPLATE ===
TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>🔥 LockBox AI Picks 🔒</title>
<style>
  body { background-color:#0d1117; color:#c9d1d9; font-family:Arial, sans-serif; margin:0; padding:0; }
  h1 { color:#58a6ff; text-align:center; padding:20px 0; }
  .updated { text-align:center; font-size:0.9rem; color:#8b949e; margin-top:-15px; }
  .filters { display:flex; justify-content:center; margin:15px; gap:10px; }
  select { background:#161b22; color:#c9d1d9; border:1px solid #30363d; padding:6px 10px; border-radius:6px; }
  .grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(320px,1fr)); gap:12px; margin:0 20px 40px; }
  .card { background:#161b22; border:1px solid #30363d; border-radius:8px; padding:16px; }
  .game-title { color:#58a6ff; font-weight:bold; font-size:1rem; margin-bottom:6px; }
  .pick { color:#e3b341; font-weight:bold; margin:4px 0; }
  .meta { font-size:0.9rem; color:#8b949e; }
  .edge { color:#3fb950; font-weight:bold; float:right; }
  .badge { background:#21262d; border-radius:4px; padding:3px 6px; font-size:0.8rem; color:#79c0ff; float:right; }
  .lock { color:#f0c420; margin-left:4px; }
  .upset { color:#f85149; margin-left:4px; }
</style>
</head>
<body>
  <h1>🔥 LockBox AI Picks 🔒</h1>
  <div class="updated">Your edge, every game — Updated: {{ updated }}</div>
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
          <span class="badge">{{ row.Sport }}</span>
          {% if row.LockEmoji %}<span class="lock">{{ row.LockEmoji }}</span>{% endif %}
          {% if row.UpsetEmoji %}<span class="upset">{{ row.UpsetEmoji }}</span>{% endif %}
        </div>
        <div class="meta">{{ row.GameTime }}</div>
        <div class="pick">{{ row.MoneylinePick }}</div>
        <div class="meta">
          Confidence: {{ "%.1f"|format(row.Confidence) }} % | Edge: {{ "%.1f"|format(row.Edge) }} %
          <br>ML: {{ row.MoneylinePick }} | ATS: {{ row.ATS }} | O/U: {{ row.OU }}
          <br>{{ row.Reason }}
        </div>
      </div>
    {% endfor %}
  </div>

  <script>
    function updateFilters(){
      const s=document.getElementById("sport").value;
      const t=document.getElementById("top5").value;
      window.location.href=`/?sport=${s}&top5=${t}`;
    }
  </script>
</body>
</html>
"""

def load_predictions():
    """Load the most recent predictions file safely."""
    primary = os.path.join(OUTPUT_DIR, PRIMARY_FILE)
    fallback = os.path.join(OUTPUT_DIR, FALLBACK_FILE)
    csv_path = primary if os.path.exists(primary) else fallback

    df = pd.read_csv(csv_path)
    df.columns = [c.strip() for c in df.columns]

    # Normalize column names
    if "Confidence(%)" in df.columns:
        df.rename(columns={"Confidence(%)": "Confidence"}, inplace=True)
    if "Edge" not in df.columns:
        df["Edge"] = 0
    if "MoneylinePick" not in df.columns:
        df["MoneylinePick"] = "N/A"
    if "Reason" not in df.columns:
        df["Reason"] = "Model vs Market probability differential"

    df["Confidence"] = pd.to_numeric(df["Confidence"], errors="coerce").fillna(0)
    df["Edge"] = df["Edge"].astype(str).str.replace("%","",regex=False).astype(float)
    df["Sport"] = df["Sport"].replace({
        "americanfootball_nfl": "NFL",
        "americanfootball_ncaaf": "CFB",
        "basketball_nba": "NBA",
        "baseball_mlb": "MLB",
        "icehockey_nhl": "NHL"
    })
    return df, os.path.basename(csv_path)

@app.route("/")
def index():
    sport = request.args.get("sport","All")
    top5 = request.args.get("top5","All")

    df, filename = load_predictions()
    sports = sorted(df["Sport"].dropna().unique())

    # Determine Lock/UpSet emojis
    df["LockEmoji"] = df.apply(lambda x: "🔒" if x["Confidence"] >= 101 else "", axis=1)
    df["UpsetEmoji"] = df.apply(lambda x: "🚨" if "Upset" in str(x.get("Reason","")).lower() else "", axis=1)

    # Filter by sport
    if sport != "All":
        df = df[df["Sport"] == sport]

    # Top 5 picks per sport by Edge×Confidence
    if top5 == "1":
        df["Score"] = df["Edge"] * df["Confidence"]
        df = df.sort_values("Score", ascending=False).head(5)

    records = df.to_dict(orient="records")
    return render_template_string(TEMPLATE, data=records, updated=filename, sports=sports, sport=sport, top5=top5)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
