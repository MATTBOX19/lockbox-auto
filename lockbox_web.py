# lockbox_web.py — LockBox Pro (API-enabled, cleaner version)
from flask import Flask, render_template_string, jsonify, request
import pandas as pd, os, glob, re
from collections import defaultdict
from datetime import datetime

app = Flask(__name__)

# === Config ===
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "/opt/render/project/src/Output")
PRIMARY_FILE = os.getenv("PRIMARY_FILE", "")
FALLBACK_FILE = os.path.join(OUTPUT_DIR, "Predictions_test.csv")
LATEST_NAME = "Predictions_latest_Explained.csv"

# Thresholds
try:
    LOCK_EDGE_THRESHOLD = float(os.getenv("LOCK_EDGE_THRESHOLD", "0.5"))
    LOCK_CONFIDENCE_THRESHOLD = float(os.getenv("LOCK_CONFIDENCE_THRESHOLD", "75.0"))
    UPSET_EDGE_THRESHOLD = float(os.getenv("UPSET_EDGE_THRESHOLD", "0.3"))
except Exception:
    LOCK_EDGE_THRESHOLD = 0.5
    LOCK_CONFIDENCE_THRESHOLD = 75.0
    UPSET_EDGE_THRESHOLD = 0.3


# === Utility ===
def compute_sport_performance():
    """Reads Output/history.csv and returns win/loss by Sport and BetType (ML/ATS/OU)."""
    path = os.path.join(OUTPUT_DIR, "history.csv")
    if not os.path.exists(path):
        return "No performance data yet."
    try:
        df = pd.read_csv(path)
    except Exception:
        return "No performance data yet."
    if df.empty:
        return "No graded bets yet."

    perf = defaultdict(lambda: {"ML": [0, 0], "ATS": [0, 0], "OU": [0, 0]})
    for _, row in df.iterrows():
        sport = str(row.get("Sport", "")).strip().upper()
        bet = str(row.get("BetType", "")).strip().upper()
        res = str(row.get("Result", "")).strip().upper()
        if sport and bet in ["ML", "ATS", "OU"]:
            if res == "WIN":
                perf[sport][bet][0] += 1
            elif res == "LOSS":
                perf[sport][bet][1] += 1

    emoji = {"NFL": "🏈", "CFB": "🎓", "NBA": "🏀", "MLB": "⚾", "NHL": "🏒"}
    out = []
    for sport, bets in perf.items():
        segs = []
        for b in ["ML", "ATS", "OU"]:
            w, l = bets[b]
            t = w + l
            if t > 0:
                pct = round(100 * w / t, 1)
                segs.append(f"{b}: {w}-{l} ({pct}%)")
        emoji_s = emoji.get(sport, "🎯")
        out.append(f"{emoji_s} {sport} — {' | '.join(segs)}")
    return " | ".join(out) if out else "No recent results yet."


def find_latest_file():
    """Locate the most recent predictions file."""
    latest = os.path.join(OUTPUT_DIR, LATEST_NAME)
    if os.path.exists(latest):
        return latest
    files = sorted(
        glob.glob(os.path.join(OUTPUT_DIR, "Predictions_*_Explained.csv")),
        key=os.path.getmtime,
        reverse=True,
    )
    if files:
        return files[0]
    if os.path.exists(FALLBACK_FILE):
        return FALLBACK_FILE
    return None


def parse_teams_from_ml(ml_value):
    """Extract team names from ML field like 'TeamA:-150 | TeamB:+130'."""
    try:
        parts = str(ml_value).split("|")
        if len(parts) >= 2:
            t1 = parts[0].split(":")[0].strip()
            t2 = parts[1].split(":")[0].strip()
            return t1, t2
    except Exception:
        pass
    return None, None


def load_predictions():
    """Load and normalize predictions CSV."""
    path = find_latest_file()
    if not path:
        return pd.DataFrame(), "NO_FILE"

    try:
        df = pd.read_csv(path)
    except Exception as e:
        print("⚠️ Could not read predictions CSV:", e)
        return pd.DataFrame(), "READ_ERROR"

    df.columns = [c.strip() for c in df.columns]
    if "Confidence(%)" in df.columns and "Confidence" not in df.columns:
        df.rename(columns={"Confidence(%)": "Confidence"}, inplace=True)
    if "MoneylinePick" not in df.columns and "BestPick" in df.columns:
        df["MoneylinePick"] = df["BestPick"]

    # fill missing team names
    if "Team1" not in df.columns:
        df["Team1"] = ""
    if "Team2" not in df.columns:
        df["Team2"] = ""
    if "ML" in df.columns:
        mask = (df["Team1"].astype(str).str.strip() == "") | (
            df["Team2"].astype(str).str.strip() == ""
        )
        for i in df[mask].index:
            t1, t2 = parse_teams_from_ml(df.at[i, "ML"])
            df.at[i, "Team1"] = t1 or ""
            df.at[i, "Team2"] = t2 or ""

    # normalize types
    df["Edge"] = pd.to_numeric(df.get("Edge", 0), errors="coerce").fillna(0.0)
    df["Confidence"] = pd.to_numeric(
        df.get("Confidence", 0), errors="coerce"
    ).fillna(0.0)
    df["EdgeDisplay"] = df["Edge"].round(3).astype(str)

    # fill emojis & normalize sport
    df["LockEmoji"] = df.get("LockEmoji", "")
    df["UpsetEmoji"] = df.get("UpsetEmoji", "")
    df["Sport_raw"] = df.get("Sport", "").astype(str)
    df["Sport"] = df["Sport_raw"].replace(
        {
            "americanfootball_nfl": "NFL",
            "americanfootball_ncaaf": "CFB",
            "basketball_nba": "NBA",
            "baseball_mlb": "MLB",
            "icehockey_nhl": "NHL",
        }
    )
    return df, os.path.basename(path)


# === HTML Template ===
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
<div class="perfbar">{{ perf_summary }}</div>
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
    sport = request.args.get("sport", "All")
    top5 = request.args.get("top5", "All")

    df, filename = load_predictions()
    if df.empty:
        msg = "No predictions available yet."
        return render_template_string(
            TEMPLATE,
            data=[],
            updated=msg,
            sports=[],
            sport=sport,
            top5=top5,
            footer_text=msg,
            perf_summary=compute_sport_performance(),
        )

    sports = sorted(df["Sport"].dropna().unique())
    if sport != "All":
        df = df[df["Sport"] == sport]
    if top5 == "1":
        df["Score"] = df["Edge"] * df["Confidence"]
        df = df.sort_values("Score", ascending=False).head(5)

    footer = f"Showing {len(df)} picks from {filename}"
    perf = compute_sport_performance()
    return render_template_string(
        TEMPLATE,
        data=df.to_dict(orient="records"),
        updated=filename,
        sports=sports,
        sport=sport,
        top5=top5,
        footer_text=footer,
        perf_summary=perf,
    )


@app.route("/api/status")
def api_status():
    """Health check."""
    df, filename = load_predictions()
    return jsonify(
        {
            "status": "ok",
            "records": len(df),
            "file": filename,
            "last_updated": datetime.utcnow().isoformat() + "Z",
        }
    )


@app.route("/api/picks")
def api_picks():
    """Return all picks in JSON form."""
    df, filename = load_predictions()
    if df.empty:
        return jsonify({"message": "no picks yet", "records": 0, "file": filename})
    return jsonify(
        {
            "records": len(df),
            "file": filename,
            "picks": df.to_dict(orient="records"),
        }
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
