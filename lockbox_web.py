from flask import Flask, render_template_string, request
import pandas as pd
import os
from pathlib import Path

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
  .grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  max-width: 1400px;
  margin: 0 auto 40px;
  gap: 14px;
  padding: 0 20px;
  .card { background:#161b22; border:1px solid #30363d; border-radius:8px; padding:16px; }
  .game-title { color:#58a6ff; font-weight:bold; font-size:1rem; margin-bottom:6px; }
  .pick { color:#e3b341; font-weight:bold; margin:4px 0; }
  .meta { font-size:0.9rem; color:#8b949e; }
  .edge { color:#3fb950; font-weight:bold; float:right; }
  .badge { background:#21262d; border-radius:4px; padding:3px 6px; font-size:0.8rem; color:#79c0ff; float:right; }
  .lock { color:#f0c420; margin-left:4px; }
  .upset { color:#f85149; margin-left:4px; }
  .footer { max-width:1400px; margin: 0 auto 30px; color:#8b949e; font-size:0.9rem; padding: 10px 20px; text-align:center; }
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
          Confidence: {{ "%.1f"|format(row.Confidence) }} % | Edge: {{ "%.2f"|format(row.Edge) }} %
          <br>ML: {{ row.ML }} | ATS: {{ row.ATS }} | O/U: {{ row.OU }}
          <br>{{ row.Reason }}
        </div>
      </div>
    {% endfor %}
  </div>

  <div class="footer">
    <strong>Performance</strong> —
    {% if perf.total == 0 %}
      No predictions available.
    {% else %}
      Total: {{ perf.total }} |
      Settled: {{ perf.settled }} |
      ML Wins: {{ perf.wins }} |
      ML Losses: {{ perf.losses }} |
      Pushes: {{ perf.pushes }} |
      Win%: {{ "%.1f"|format(perf.win_pct) }}%
    {% endif %}
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

    if not os.path.exists(csv_path):
        # try to use the newest file in Output as last resort
        files = sorted([os.path.join(OUTPUT_DIR, f) for f in os.listdir(OUTPUT_DIR) if f.startswith("Predictions_")])
        csv_path = files[-1] if files else None

    if not csv_path or not os.path.exists(csv_path):
        # return empty df
        df = pd.DataFrame(columns=["Sport","GameTime","Team1","Team2","MoneylinePick","Confidence","Edge","ML","ATS","OU","Reason","LockEmoji","UpsetEmoji"])
        return df, "None"

    df = pd.read_csv(csv_path)
    df.columns = [c.strip() for c in df.columns]

    # Normalize column names
    if "Confidence(%)" in df.columns:
        df.rename(columns={"Confidence(%)": "Confidence"}, inplace=True)
    if "Edge" in df.columns:
        # remove % if present, otherwise convert numeric
        df["Edge"] = df["Edge"].astype(str).str.replace("%","",regex=False)
    if "Edge" not in df.columns:
        df["Edge"] = 0

    # Ensure numeric types and safe defaults
    df["Confidence"] = pd.to_numeric(df.get("Confidence", 0), errors="coerce").fillna(0)
    df["Edge"] = pd.to_numeric(df.get("Edge", 0), errors="coerce").fillna(0.0)

    if "MoneylinePick" not in df.columns:
        df["MoneylinePick"] = "N/A"
    # Ensure emojis are strings
    for col in ["LockEmoji","UpsetEmoji"]:
        if col not in df.columns:
            df[col] = ""
        else:
            df[col] = df[col].fillna("").astype(str)

    df["Sport"] = df["Sport"].replace({
        "americanfootball_nfl": "NFL",
        "americanfootball_ncaaf": "CFB",
        "basketball_nba": "NBA",
        "baseball_mlb": "MLB",
        "icehockey_nhl": "NHL"
    })
    return df, os.path.basename(csv_path)

def compute_performance():
    """
    Read the latest Settled CSV if present (Predictions_*_Settled.csv),
    otherwise try the latest Explained CSV and compute simple ML stats.
    """
    out = Path(OUTPUT_DIR)
    settled_files = sorted(out.glob("Predictions_*_Settled.csv"))
    explained_files = sorted(out.glob("Predictions_*_Explained.csv"))

    path = settled_files[-1] if settled_files else (explained_files[-1] if explained_files else None)
    if not path:
        return {"total": 0, "settled": 0, "wins": 0, "losses": 0, "pushes": 0, "win_pct": 0.0}

    df = pd.read_csv(path)
    cols = [c.strip() for c in df.columns]

    total = len(df)
    # Settle-aware columns
    ml_col = "ML_Result" if "ML_Result" in cols else None
    settled_mask = df[ml_col].notna() & (df[ml_col].astype(str).str.strip() != "") if ml_col else pd.Series([False]*len(df))

    settled = int(settled_mask.sum()) if len(df)>0 else 0
    wins = int((df[ml_col].astype(str).str.upper() == "W").sum()) if ml_col else 0
    losses = int((df[ml_col].astype(str).str.upper() == "L").sum()) if ml_col else 0
    pushes = int((df[ml_col].astype(str).str.upper() == "PUSH").sum()) if ml_col else 0
    win_pct = (wins / settled * 100.0) if settled>0 else 0.0

    return {"total": total, "settled": settled, "wins": wins, "losses": losses, "pushes": pushes, "win_pct": win_pct}

@app.route("/")
def index():
    sport = request.args.get("sport","All")
    top5 = request.args.get("top5","All")

    df, filename = load_predictions()
    sports = sorted(df["Sport"].dropna().unique())

    # Determine Lock/UpSet emojis (fallback if CSV doesn't provide them)
    df["LockEmoji"] = df.apply(lambda x: x.get("LockEmoji","") if str(x.get("LockEmoji","")).strip() else ("🔒" if float(x["Edge"]) >= 4 and float(x["Confidence"]) >= 60 else ""), axis=1)
    df["UpsetEmoji"] = df.apply(lambda x: x.get("UpsetEmoji","") if str(x.get("UpsetEmoji","")).strip() else ("🚨" if float(x["Edge"]) >= 2 and (x.get("MoneylinePick") not in [x["Team1"], x["Team2"]])==False and float(x["Edge"])>0 and float(x["Confidence"])<50 else ""), axis=1)

    # Filter by sport
    if sport != "All":
        df = df[df["Sport"] == sport]

    # Top 5 picks per sport by Edge×Confidence
    if top5 == "1":
        df["Score"] = df["Edge"] * df["Confidence"]
        df = df.sort_values("Score", ascending=False).head(5)

    records = df.to_dict(orient="records")
    perf = compute_performance()
    return render_template_string(TEMPLATE, data=records, updated=filename, sports=sports, sport=sport, top5=top5, perf=perf)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
