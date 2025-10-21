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
LATEST_FILE = os.path.join(OUTPUT_DIR, "Predictions_latest_Explained.csv")

# Thresholds (match predictor defaults; can override in Render env)
try:
    LOCK_EDGE_THRESHOLD = float(os.getenv("LOCK_EDGE_THRESHOLD", "0.5"))
    LOCK_CONFIDENCE_THRESHOLD = float(os.getenv("LOCK_CONFIDENCE_THRESHOLD", "51.0"))
    UPSET_EDGE_THRESHOLD = float(os.getenv("UPSET_EDGE_THRESHOLD", "0.3"))
except Exception:
    LOCK_EDGE_THRESHOLD = 0.5
    LOCK_CONFIDENCE_THRESHOLD = 51.0
    UPSET_EDGE_THRESHOLD = 0.3

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
          Confidence: {{ "%.1f"|format(row.Confidence if row.Confidence is not none else 0) }} % | Edge: {{ "%.2f"|format(row.Edge if row.Edge is not none else 0) }} %
          <br>ML: {{ row.ML }} | ATS: {{ row.ATS }} | O/U: {{ row.OU }}
          <br>{{ row.Reason }}
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
    """
    Prefer a 'latest' pinned filename, then PRIMARY_FILE, then newest datestamped Predictions_*_Explained.csv,
    then fallback.
    """
    # 1) explicit latest file created by predictor
    if os.path.exists(LATEST_FILE):
        return LATEST_FILE

    # 2) if PRIMARY_FILE env var set, use it
    if PRIMARY_FILE:
        p = os.path.join(OUTPUT_DIR, PRIMARY_FILE)
        if os.path.exists(p):
            return p

    # 3) pick newest Predictions_*_Explained.csv
    files = glob.glob(os.path.join(OUTPUT_DIR, "Predictions_*_Explained.csv"))
    if files:
        files.sort(key=os.path.getmtime, reverse=True)
        return files[0]

    # 4) fallback test file
    if os.path.exists(FALLBACK_FILE):
        return FALLBACK_FILE

    return None

def load_predictions():
    csv_path = find_latest_file()
    if not csv_path:
        df = pd.DataFrame(columns=["Sport","GameTime","Team1","Team2","MoneylinePick","Confidence","Edge","ML","ATS","OU","Reason","LockEmoji","UpsetEmoji"])
        return df, "NO_FILE"

    # Debug prints - so you can see in logs which file the app chose
    print("DEBUG: CSV path chosen by web app:", csv_path, file=sys.stderr)
    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        print("ERROR: Failed to read CSV:", e, file=sys.stderr)
        df = pd.DataFrame(columns=["Sport","GameTime","Team1","Team2","MoneylinePick","Confidence","Edge","ML","ATS","OU","Reason","LockEmoji","UpsetEmoji"])
        return df, os.path.basename(csv_path)

    # Trim whitespace in column names
    df.columns = [c.strip() for c in df.columns]

    # Very defensive normalization for Confidence column variants
    if "Confidence(%)" in df.columns and "Confidence" not in df.columns:
        df.rename(columns={"Confidence(%)": "Confidence"}, inplace=True)

    # Edge: can be stored as numeric or string like "1.23%" — normalize to numeric float
    if "Edge" in df.columns:
        df["Edge"] = df["Edge"].astype(str).str.replace("%", "", regex=False)
        df["Edge"] = pd.to_numeric(df["Edge"], errors="coerce").fillna(0.0)
    else:
        df["Edge"] = 0.0

    # Confidence numeric
    df["Confidence"] = pd.to_numeric(df.get("Confidence", 0), errors="coerce").fillna(0.0)

    # Ensure ML/ATS/OU columns exist
    for col in ["ML", "ATS", "OU"]:
        if col not in df.columns:
            df[col] = ""

    # Ensure LockEmoji/UpsetEmoji exist and cast to string
    if "LockEmoji" not in df.columns:
        df["LockEmoji"] = ""
    else:
        df["LockEmoji"] = df["LockEmoji"].fillna("").astype(str)
    if "UpsetEmoji" not in df.columns:
        df["UpsetEmoji"] = ""
    else:
        df["UpsetEmoji"] = df["UpsetEmoji"].fillna("").astype(str)

    # Map any long sport keys to friendly labels if present
    # If predictor already outputs 'CFB','NFL' etc, this won't change them.
    df["Sport_raw"] = df["Sport"].astype(str)
    df["Sport"] = df["Sport"].replace({
        "americanfootball_nfl": "NFL",
        "americanfootball_ncaaf": "CFB",
        "americanfootball_ncaa": "CFB",
        "basketball_nba": "NBA",
        "baseball_mlb": "MLB",
        "icehockey_nhl": "NHL"
    })

    # Debugging: show first rows & sport lists
    try:
        print("DEBUG: CSV head (first rows):", file=sys.stderr)
        print(df.head(6).to_string(index=False), file=sys.stderr)
    except Exception:
        pass
    try:
        raw_unique = sorted(df["Sport_raw"].dropna().unique().tolist())
        mapped_unique = sorted(df["Sport"].dropna().unique().tolist())
        print("DEBUG: raw unique Sport values in CSV:", raw_unique, file=sys.stderr)
        print("DEBUG: mapped unique Sport values after normalization:", mapped_unique, file=sys.stderr)
    except Exception:
        pass

    return df, os.path.basename(csv_path)

@app.route("/")
def index():
    sport = request.args.get("sport", "All")
    top5 = request.args.get("top5", "All")

    df, filename = load_predictions()

    # compute missing emojis with thresholds if empty
    try:
        mask_missing_lock = df["LockEmoji"].astype(str).str.strip() == ""
        df.loc[mask_missing_lock, "LockEmoji"] = df[mask_missing_lock].apply(
            lambda r: "🔒" if (float(r.get("Edge", 0) or 0) >= LOCK_EDGE_THRESHOLD and float(r.get("Confidence", 0) or 0) >= LOCK_CONFIDENCE_THRESHOLD) else "",
            axis=1
        )
    except Exception:
        pass

    try:
        mask_missing_upset = df["UpsetEmoji"].astype(str).str.strip() == ""
        df.loc[mask_missing_upset, "UpsetEmoji"] = df[mask_missing_upset].apply(
            lambda r: "🚨" if (float(r.get("Edge", 0) or 0) >= UPSET_EDGE_THRESHOLD and float(r.get("Confidence", 0) or 0) < 52) else "",
            axis=1
        )
    except Exception:
        pass

    # filter by sport if requested
    if sport != "All":
        df = df[df["Sport"] == sport]

    # top 5 selection
    if top5 == "1":
        df["Score"] = df["Edge"].astype(float) * df["Confidence"].astype(float)
        df = df.sort_values("Score", ascending=False).head(5)

    # footer summary
    footer_text = f"Showing {len(df)} picks from {filename}"
    if "Settled" in df.columns:
        total = len(df)
        needs = int((df["Settled"] == "NEEDS_SETTLING").sum())
        auto = int((df["Settled"] == "AUTO").sum())
        footer_text = f"Settled: AUTO={auto} | NEEDS_SETTLING={needs} | Total shown={total}"

    records = df.to_dict(orient="records")
    return render_template_string(TEMPLATE, data=records, updated=filename, sports=sorted(df["Sport"].dropna().unique()), sport=sport, top5=top5, footer_text=footer_text)

if __name__ == "__main__":
    # Print a small startup note
    print("Starting lockbox_web.py - web app will prefer Predictions_latest_Explained.csv if present", file=sys.stderr)
    app.run(host="0.0.0.0", port=10000)
