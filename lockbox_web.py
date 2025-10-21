from flask import Flask, render_template_string, request
import pandas as pd
import os
from pathlib import Path
import glob
import sys

app = Flask(__name__)

# Config (can override via env)
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "/opt/render/project/src/Output")
PRIMARY_FILE = os.getenv("PRIMARY_FILE", "")
FALLBACK_FILE = os.path.join(OUTPUT_DIR, "Predictions_test.csv")

# Thresholds (match predictor defaults; can override in Render env)
try:
    LOCK_EDGE_THRESHOLD = float(os.getenv("LOCK_EDGE_THRESHOLD", "0.5"))
    LOCK_CONFIDENCE_THRESHOLD = float(os.getenv("LOCK_CONFIDENCE_THRESHOLD", "51.0"))
    UPSET_EDGE_THRESHOLD = float(os.getenv("UPSET_EDGE_THRESHOLD", "0.3"))
except Exception:
    LOCK_EDGE_THRESHOLD = 0.5
    LOCK_CONFIDENCE_THRESHOLD = 51.0
    UPSET_EDGE_THRESHOLD = 0.3

# Friendly sport mapping (lowercase keys)
SPORT_MAP = {
    "americanfootball_nfl": "NFL",
    "americanfootball_ncaaf": "CFB",
    "americanfootball_ncaa": "CFB",
    "basketball_nba": "NBA",
    "baseball_mlb": "MLB",
    "icehockey_nhl": "NHL"
}

# HTML template (unchanged)
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
  }
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
      <option value="{{s}}" {% if s==sport %}selected{% endif %}>
        {% if s == 'CFB' %}CFB – College Football{% else %}{{s}}{% endif %}
      </option>
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
          Confidence: {{ "%.1f"|format(row.get('Confidence', 0)) }} % | Edge: {{ "%.2f"|format(row.get('Edge', 0)) }} %
          <br>ML: {{ row.get('ML','') }} | ATS: {{ row.get('ATS','') }} | O/U: {{ row.get('OU','') }}
          <br>{{ row.get('Reason','') }}
        </div>
      </div>
    {% endfor %}
  </div>

  <div class="footer">
    {% if footer_text %}
      {{ footer_text }}
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

def find_latest_file():
    # If PRIMARY_FILE env var is set and exists, use it.
    if PRIMARY_FILE:
        p = os.path.join(OUTPUT_DIR, PRIMARY_FILE)
        if os.path.exists(p):
            return p
    # Otherwise pick newest Predictions_*_Explained.csv
    files = glob.glob(os.path.join(OUTPUT_DIR, "Predictions_*_Explained.csv"))
    if not files:
        f = FALLBACK_FILE if os.path.exists(FALLBACK_FILE) else None
        return f
    files.sort(key=os.path.getmtime, reverse=True)
    return files[0]

def load_predictions():
    csv_path = find_latest_file()

    # --- DEBUG: which file are we using? ---
    print("DEBUG: CSV path chosen by web app:", csv_path, file=sys.stdout)

    if not csv_path:
        df = pd.DataFrame(columns=["Sport","GameTime","Team1","Team2","MoneylinePick","Confidence","Edge","ML","ATS","OU","Reason","LockEmoji","UpsetEmoji"])
        return df, "NO_FILE"

    # Read CSV
    df = pd.read_csv(csv_path)
    df.columns = [c.strip() for c in df.columns]

    # --- DEBUG: show head and raw unique sports ---
    try:
        print("DEBUG: CSV head (first rows):")
        print(df.head(8).to_string(), file=sys.stdout)
    except Exception as e:
        print("DEBUG: could not print head:", e, file=sys.stdout)

    # show raw unique values in Sport column (if present)
    if "Sport" in df.columns:
        raw_unique = df["Sport"].dropna().astype(str).str.strip().unique().tolist()
        print("DEBUG: raw unique Sport values in CSV:", raw_unique, file=sys.stdout)
    else:
        print("DEBUG: CSV has no 'Sport' column. Columns:", df.columns.tolist(), file=sys.stdout)

    # backwards-compatibility: rename Confidence(%) -> Confidence
    if "Confidence(%)" in df.columns and "Confidence" not in df.columns:
        df.rename(columns={"Confidence(%)": "Confidence"}, inplace=True)

    # Edge cleaning: remove "%" if present and coerce to float
    if "Edge" in df.columns:
        df["Edge"] = df["Edge"].astype(str).str.replace("%","",regex=False)
        df["Edge"] = pd.to_numeric(df["Edge"], errors="coerce").fillna(0.0)
    else:
        df["Edge"] = 0.0

    # Confidence numeric
    df["Confidence"] = pd.to_numeric(df.get("Confidence", 0), errors="coerce").fillna(0.0)

    # Ensure ML/ATS/OU columns exist
    if "ML" not in df.columns:
        df["ML"] = df.get("Moneyline","")
    if "ATS" not in df.columns:
        df["ATS"] = ""
    if "OU" not in df.columns:
        df["OU"] = ""

    # Ensure LockEmoji/UpsetEmoji exist and are strings (avoid NaN)
    df["LockEmoji"] = df.get("LockEmoji", "").fillna("").astype(str)
    df["UpsetEmoji"] = df.get("UpsetEmoji", "").fillna("").astype(str)

    # Normalize Sport values robustly (lowercase keys)
    if "Sport" in df.columns:
        df["Sport"] = df["Sport"].astype(str).str.strip()
        # map known raw keys to friendly names (case-insensitive)
        df["Sport"] = df["Sport"].apply(lambda v: SPORT_MAP.get(v.lower(), v))

        # --- DEBUG: show mapped unique sports ---
        mapped_unique = df["Sport"].dropna().unique().tolist()
        print("DEBUG: mapped unique Sport values after normalization:", mapped_unique, file=sys.stdout)

    else:
        print("DEBUG: 'Sport' column missing after reading CSV.", file=sys.stdout)

    return df, os.path.basename(csv_path)

@app.route("/")
def index():
    sport = request.args.get("sport","All")
    top5 = request.args.get("top5","All")

    df, filename = load_predictions()
    sports = sorted(df["Sport"].dropna().unique())

    try:
        mask_missing_lock = df["LockEmoji"].astype(str).str.strip() == ""
        df.loc[mask_missing_lock, "LockEmoji"] = df[mask_missing_lock].apply(
            lambda r: "🔒" if (r.get("Edge",0) >= LOCK_EDGE_THRESHOLD and r.get("Confidence",0) >= LOCK_CONFIDENCE_THRESHOLD) else "",
            axis=1
        )
    except Exception:
        pass

    try:
        mask_missing_upset = df["UpsetEmoji"].astype(str).str.strip() == ""
        df.loc[mask_missing_upset, "UpsetEmoji"] = df[mask_missing_upset].apply(
            lambda r: "🚨" if (r.get("Edge",0) >= UPSET_EDGE_THRESHOLD and r.get("Confidence",0) < 52) else "",
            axis=1
        )
    except Exception:
        pass

    if sport != "All":
        df = df[df["Sport"] == sport]

    if top5 == "1":
        df["Score"] = df["Edge"].astype(float) * df["Confidence"].astype(float)
        df = df.sort_values("Score", ascending=False).head(5)

    footer_text = f"Showing {len(df)} picks from {filename}"
    if "Settled" in df.columns:
        total = len(df)
        needs = int((df["Settled"] == "NEEDS_SETTLING").sum())
        auto = int((df["Settled"] == "AUTO").sum())
        footer_text = f"Settled: AUTO={auto} | NEEDS_SETTLING={needs} | Total shown={total}"

    records = df.to_dict(orient="records")
    return render_template_string(TEMPLATE, data=records, updated=filename, sports=sports, sport=sport, top5=top5, footer_text=footer_text)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
