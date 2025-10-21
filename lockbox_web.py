from flask import Flask, render_template_string, request
import pandas as pd
import os
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
          Confidence: {{ "%.1f"|format(row.Confidence|default(0)) }} % | Edge: {{ "%.2f"|format(row.Edge|default(0)) }} %
          <br>ML: {{ row.ML|default('') }} | ATS: {{ row.ATS|default('') }} | O/U: {{ row.OU|default('') }}
          <br>{{ row.Reason|default('') }}
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
  // auto-refresh every 60s so front-end picks up new Predictions_latest_Explained.csv.
  setTimeout(()=>{ window.location.reload(); }, 60000);
</script>
</body>
</html>
"""

def find_latest_file():
    """
    Return a path to the CSV to use. Priority:
      1) PRIMARY_FILE env var (if exists in OUTPUT_DIR)
      2) Predictions_latest_Explained.csv (explicit latest file)
      3) newest Predictions_*_Explained.csv by mtime
      4) FALLBACK_FILE if exists
      5) None
    """
    # 1) PRIMARY_FILE
    if PRIMARY_FILE:
        p = os.path.join(OUTPUT_DIR, PRIMARY_FILE)
        if os.path.exists(p):
            print(f"DEBUG: PRIMARY_FILE chosen: {p}", file=sys.stderr)
            return p

    # 2) explicit latest file (predictor writes this intentionally)
    latest_path = os.path.join(OUTPUT_DIR, "Predictions_latest_Explained.csv")
    if os.path.exists(latest_path):
        print(f"DEBUG: Found explicit latest file: {latest_path}", file=sys.stderr)
        return latest_path

    # 3) fallback to newest Predictions_*_Explained.csv
    files = glob.glob(os.path.join(OUTPUT_DIR, "Predictions_*_Explained.csv"))
    if not files:
        f = FALLBACK_FILE if os.path.exists(FALLBACK_FILE) else None
        if f:
            print(f"DEBUG: No Predictions_* files; using fallback: {f}", file=sys.stderr)
        else:
            print("DEBUG: No prediction CSV found at all", file=sys.stderr)
        return f
    files.sort(key=os.path.getmtime, reverse=True)
    chosen = files[0]
    print(f"DEBUG: Chosen newest Predictions_* file by mtime: {chosen}", file=sys.stderr)
    return chosen

def coerce_numeric_column(df, colname, percent_strip=True, default=0.0):
    """Ensure a numeric column exists and is numeric. Return df with column."""
    if colname in df.columns:
        s = df[colname].astype(str)
        if percent_strip:
            s = s.str.replace("%", "", regex=False)
        df[colname] = pd.to_numeric(s, errors="coerce").fillna(default)
    else:
        df[colname] = default
    return df

def load_predictions():
    csv_path = find_latest_file()
    if not csv_path:
        # return empty df
        df = pd.DataFrame(columns=["Sport","GameTime","Team1","Team2","MoneylinePick","Confidence","Edge","ML","ATS","OU","Reason","LockEmoji","UpsetEmoji"])
        return df, "NO_FILE"

    # DEBUG: print chosen CSV
    print(f"DEBUG: CSV path chosen by web app: {csv_path}", file=sys.stderr)

    # read CSV defensively
    try:
        df = pd.read_csv(csv_path, dtype=str)
    except Exception as e:
        print(f"ERROR: Failed to read CSV {csv_path}: {e}", file=sys.stderr)
        # fall back to empty
        df = pd.DataFrame(columns=["Sport","GameTime","Team1","Team2","MoneylinePick","Confidence","Edge","ML","ATS","OU","Reason","LockEmoji","UpsetEmoji"])
        return df, os.path.basename(csv_path)

    # strip whitespace from column names
    df.columns = [c.strip() for c in df.columns]

    # DEBUG: show head (first 8 rows) and columns
    try:
        print("DEBUG: CSV head (first rows):", file=sys.stderr)
        print(df.head(8).to_string(index=False), file=sys.stderr)
    except Exception:
        pass
    try:
        print("DEBUG: CSV columns:", df.columns.tolist(), file=sys.stderr)
    except Exception:
        pass

    # normalize column name variants
    if "Confidence(%)" in df.columns and "Confidence" not in df.columns:
        df.rename(columns={"Confidence(%)": "Confidence"}, inplace=True)

    # sometimes predictor uses HomeTeam/AwayTeam or Team1/Team2 -> normalize to Team1/Team2
    if "HomeTeam" in df.columns and "Team1" not in df.columns:
        df["Team1"] = df["HomeTeam"]
    if "AwayTeam" in df.columns and "Team2" not in df.columns:
        df["Team2"] = df["AwayTeam"]

    # ensure Team1/Team2 exist (if predictor used different column names)
    if "Team1" not in df.columns:
        df["Team1"] = df.iloc[:, df.columns.get_loc('Team1')] if 'Team1' in df.columns else ""
    if "Team2" not in df.columns:
        df["Team2"] = df.iloc[:, df.columns.get_loc('Team2')] if 'Team2' in df.columns else ""

    # Edge cleaning: remove "%" if present and coerce to float
    # predictor sometimes writes "Edge" as "12.34%" or as numeric string. Always produce numeric.
    df = coerce_numeric_column(df, "Edge", percent_strip=True, default=0.0)

    # Confidence numeric
    # predictor might have "Confidence" as percent number or string. Ensure numeric.
    df = coerce_numeric_column(df, "Confidence", percent_strip=False, default=0.0)

    # If Confidence was given as a small decimal (0.5 -> 50), detect and scale up if needed.
    # Heuristic: if mean(confidence) <= 1.5 then likely in 0-1 format; scale by 100.
    try:
        mean_conf = df["Confidence"].astype(float).mean()
        if mean_conf <= 1.5 and mean_conf > 0:
            print("DEBUG: Scaling Confidence by 100 (detected 0-1 probabilities).", file=sys.stderr)
            df["Confidence"] = df["Confidence"].astype(float) * 100.0
    except Exception:
        pass

    # Ensure ML/ATS/OU columns exist (fill with empty strings if absent)
    for col in ["ML", "ATS", "OU", "Reason"]:
        if col not in df.columns:
            df[col] = ""

    # Ensure LockEmoji/UpsetEmoji exist and are strings (avoid NaN)
    if "LockEmoji" not in df.columns:
        df["LockEmoji"] = ""
    else:
        df["LockEmoji"] = df["LockEmoji"].fillna("").astype(str)
    if "UpsetEmoji" not in df.columns:
        df["UpsetEmoji"] = ""
    else:
        df["UpsetEmoji"] = df["UpsetEmoji"].fillna("").astype(str)

    # Some predictor outputs wrote a 'Sport_raw' or had sport codes; capture raw then map
    sport_raw_col = None
    for candidate in ["Sport", "Sport_raw", "sport"]:
        if candidate in df.columns:
            sport_raw_col = candidate
            break

    if sport_raw_col and sport_raw_col != "Sport":
        df["Sport_raw"] = df[sport_raw_col]
    elif sport_raw_col == "Sport":
        df["Sport_raw"] = df["Sport"]
    else:
        df["Sport_raw"] = ""

    # DEBUG: raw unique sport values before normalization
    try:
        raw_unique = sorted([x for x in df["Sport_raw"].dropna().unique().tolist() if x != ""])
        print("DEBUG: raw unique Sport values in CSV:", raw_unique, file=sys.stderr)
    except Exception:
        pass

    # Convert Sport codes to friendly names if needed
    df["Sport"] = df["Sport_raw"].replace({
        "americanfootball_nfl": "NFL",
        "americanfootball_ncaaf": "CFB",
        "americanfootball_ncaa": "CFB",
        "americanfootball": "NFL",
        "basketball_nba": "NBA",
        "baseball_mlb": "MLB",
        "icehockey_nhl": "NHL"
    })
    # If mapping produced empty values, also try any existing Sport column values
    if df["Sport"].isnull().all() or (df["Sport"] == "").all():
        if "Sport" in df.columns:
            df["Sport"] = df["Sport"].fillna("").replace({
                "americanfootball_nfl": "NFL",
                "americanfootball_ncaaf": "CFB",
                "americanfootball_ncaa": "CFB",
                "basketball_nba": "NBA",
                "baseball_mlb": "MLB",
                "icehockey_nhl": "NHL"
            })
    # final fallback: if still empty, set to "UNKNOWN"
    df["Sport"] = df["Sport"].fillna("").replace("", "UNKNOWN")

    # DEBUG: mapped unique sport values
    try:
        mapped_unique = sorted([x for x in df["Sport"].dropna().unique().tolist()])
        print("DEBUG: mapped unique Sport values after normalization:", mapped_unique, file=sys.stderr)
    except Exception:
        pass

    # Final numeric ensures
    df["Edge"] = pd.to_numeric(df["Edge"], errors="coerce").fillna(0.0)
    df["Confidence"] = pd.to_numeric(df["Confidence"], errors="coerce").fillna(0.0)

    return df, os.path.basename(csv_path)

@app.route("/")
def index():
    sport = request.args.get("sport","All")
    top5 = request.args.get("top5","All")

    df, filename = load_predictions()
    # Build sports dropdown list from df
    sports = sorted([s for s in df["Sport"].dropna().unique().tolist() if s != "UNKNOWN"])

    # Compute Lock/Upset if missing per-row
    try:
        mask_missing_lock = df["LockEmoji"].astype(str).str.strip() == ""
        df.loc[mask_missing_lock, "LockEmoji"] = df[mask_missing_lock].apply(
            lambda r: "🔒" if (float(r.get("Edge",0)) >= LOCK_EDGE_THRESHOLD and float(r.get("Confidence",0)) >= LOCK_CONFIDENCE_THRESHOLD) else "",
            axis=1
        )
    except Exception:
        pass

    try:
        mask_missing_upset = df["UpsetEmoji"].astype(str).str.strip() == ""
        df.loc[mask_missing_upset, "UpsetEmoji"] = df[mask_missing_upset].apply(
            lambda r: "🚨" if (float(r.get("Edge",0)) >= UPSET_EDGE_THRESHOLD and float(r.get("Confidence",0)) < 52) else "",
            axis=1
        )
    except Exception:
        pass

    # Filter by sport
    if sport != "All":
        df = df[df["Sport"] == sport]

    # Top 5 picks per sport by Edge×Confidence (if requested)
    if top5 == "1":
        # ensure Score exists as numeric
        try:
            df["Score"] = df["Edge"].astype(float) * df["Confidence"].astype(float)
            df = df.sort_values("Score", ascending=False).head(5)
        except Exception:
            pass

    # Footer: show settled counts if present (keeps existing behavior)
    footer_text = f"Showing {len(df)} picks from {filename}"
    if "Settled" in df.columns:
        total = len(df)
        needs = int((df["Settled"] == "NEEDS_SETTLING").sum())
        auto = int((df["Settled"] == "AUTO").sum())
        footer_text = f"Settled: AUTO={auto} | NEEDS_SETTLING={needs} | Total shown={total}"

    # Convert to records for template; also ensure expected keys exist and types are safe
    records = []
    for r in df.to_dict(orient="records"):
        rec = {
            "Sport": r.get("Sport","UNKNOWN"),
            "GameTime": r.get("GameTime",""),
            "Team1": r.get("Team1", r.get("HomeTeam", "")) or "",
            "Team2": r.get("Team2", r.get("AwayTeam", "")) or "",
            "MoneylinePick": r.get("MoneylinePick", r.get("Moneyline", "")) or "",
            "Confidence": float(r.get("Confidence") or 0.0),
            "Edge": float(r.get("Edge") or 0.0),
            "ML": r.get("ML",""),
            "ATS": r.get("ATS",""),
            "OU": r.get("OU",""),
            "Reason": r.get("Reason",""),
            "LockEmoji": r.get("LockEmoji","") or "",
            "UpsetEmoji": r.get("UpsetEmoji","") or ""
        }
        records.append(rec)

    return render_template_string(TEMPLATE, data=records, updated=filename, sports=sports, sport=sport, top5=top5, footer_text=footer_text)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
