# lockbox_web.py
#
# Flask app to show LockBox predictions.
# Looks for latest CSV under Output/Predictions_*.csv
# Robust column lookup and percent/number parsing, shows Lock / Upset badges,
# ML / ATS / O/U when present, Top-5 toggle, Sport dropdown.

from flask import Flask, request, render_template_string
import pandas as pd
import glob, os, datetime, re

app = Flask(__name__)

TEMPLATE = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>LockBox AI Picks</title>
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <style>
    :root{
      --bg:#0b0f12;
      --card:#0f1920;
      --muted:#9aa6b2;
      --accent:#29a3ff;
      --gold:#d4a10a;
      --pill:#091619;
      --text:#dbe7ef;
    }
    html,body{height:100%;margin:0;background:var(--bg);color:var(--text);font-family:Inter,system-ui,Segoe UI,Roboto,Arial;}
    .wrap{max-width:1200px;margin:28px auto;padding:20px;}
    header{display:flex;gap:12px;align-items:center;flex-wrap:wrap;justify-content:space-between}
    h1{margin:0;font-size:28px;color:var(--accent)}
    .subtitle{color:var(--muted);font-size:14px;margin-top:6px}
    .controls{display:flex;gap:10px;align-items:center}
    select,button{background:var(--pill);border:1px solid rgba(255,255,255,0.03);color:var(--text);padding:10px;border-radius:8px;font-size:14px}
    .toggle {display:inline-flex;align-items:center;gap:8px}
    .cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:18px;margin-top:22px}
    .card{background:linear-gradient(180deg, rgba(255,255,255,0.01), rgba(255,255,255,0.00));border-radius:12px;padding:18px;border:1px solid rgba(255,255,255,0.03);box-shadow: 0 4px 18px rgba(0,0,0,0.6)}
    .card h3{margin:0;color:#6ed0ff;font-size:16px}
    .meta{font-size:12px;color:var(--muted);margin-top:8px}
    .pick{margin-top:14px;font-weight:700;color:var(--gold);font-size:16px}
    .row{display:flex;justify-content:space-between;align-items:center;margin-top:10px}
    .small{font-size:13px;color:var(--muted)}
    .badge{background:rgba(255,255,255,0.03);padding:6px 8px;border-radius:8px;font-size:12px}
    .siren{color:#ff5c5c;margin-left:8px}
    .lock{margin-left:8px}
    .topbar-left{display:flex;flex-direction:column}
    .controls .btn-primary{background:var(--accent);border:none;color:#022;box-shadow: inset 0 -1px 0 rgba(0,0,0,0.2)}
    .info-row{margin-top:6px;color:var(--muted);font-size:13px}
    .small-bits{display:flex;gap:8px;align-items:center}
    .sport-pill{background:#062128;color:var(--accent);padding:6px 8px;border-radius:8px;font-weight:600;font-size:12px}
    .no-data{color:var(--muted);padding:40px;text-align:center}
    @media (max-width:620px){.cards{grid-template-columns:1fr}}
  </style>
</head>
<body>
  <div class="wrap">
    <header>
      <div class="topbar-left">
        <h1>🔥 LockBox AI Picks <span style="font-size:14px">🔒</span></h1>
        <div class="subtitle">Your edge, every game — Updated: {{ updated_at }}</div>
      </div>

      <div class="controls">
        <div>
          <label for="sport">Sport</label><br>
          <select id="sport" onchange="applyFilter()">
            <option value="All" {% if selected_sport=='All' %}selected{% endif %}>All</option>
            {% for opt in sport_options %}
              <option value="{{opt}}" {% if opt==selected_sport %}selected{% endif %}>{{opt}}</option>
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
      <div class="no-data">No predictions found. Make sure there's a CSV at <code>Output/Predictions_*.csv</code></div>
    {% else %}
      <div style="margin-top:18px;font-size:13px;color:var(--muted)">{{rows|length}} picks shown</div>
      <div class="cards">
        {% for r in rows %}
        <div class="card">
          <div style="display:flex;justify-content:space-between;align-items:flex-start">
            <div style="flex:1">
              <h3>{{ r.title }}</h3>
              <div class="meta">{{ r.gametime }}</div>
            </div>
            <div style="margin-left:12px;text-align:right">
              <div class="sport-pill">{{ r.sport }}</div>
              <div style="margin-top:8px;font-weight:700">{{ r.edge }}</div>
            </div>
          </div>

          <div class="pick">{{ r.pick if r.pick and r.pick!='N/A' else 'N/A' }}
            {% if r.lock %}<span class="lock">🔒</span>{% endif %}
            {% if r.upset %}<span class="siren">🚨</span>{% endif %}
          </div>

          <div class="info-row">
            <span class="small-bits"><strong>Confidence:</strong> {{ r.confidence }}</span>
            <span class="small-bits" style="margin-left:14px"><strong>Edge:</strong> {{ r.edge }}</span>
          </div>

          <div class="row" style="margin-top:12px">
            <div class="small">
              <div>ML: <strong>{{ r.ml }}</strong></div>
              <div>ATS: <strong>{{ r.ats }}</strong></div>
              <div>O/U: <strong>{{ r.ou }}</strong></div>
            </div>
            <div style="text-align:right" class="small">
              <div>{{ r.reason }}</div>
            </div>
          </div>

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

def find_latest_prediction_csv():
    patterns = ["Output/Predictions_*.csv", "Output/*.csv", "Predictions_*.csv"]
    candidates = []
    for p in patterns:
        candidates.extend(glob.glob(p))
    if not candidates:
        return None
    candidates = sorted(candidates, key=lambda x: os.path.getmtime(x), reverse=True)
    return candidates[0]

def find_col(df, candidates):
    cols = {c.lower(): c for c in df.columns}
    for cand in candidates:
        if cand is None:
            continue
        cl = cand.lower()
        if cl in cols:
            return cols[cl]
    for cand in candidates:
        if cand is None:
            continue
        cl = cand.lower()
        for c in df.columns:
            if cl in c.lower():
                return c
    return None

def parse_percentish(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    s = str(v).strip()
    if s == "":
        return None
    s2 = s.replace("%","").replace(",","").strip()
    try:
        return float(s2)
    except:
        return None

def parse_moneyline_numeric(s):
    if s is None:
        return None
    s = str(s).strip()
    m = re.search(r'([+-]?\d+)', s)
    if m:
        try:
            return int(m.group(1))
        except:
            return None
    return None

def normalize_sport_name(s):
    if not s:
        return "Unknown"
    s = str(s).strip().lower()
    if "nfl" in s or "americanfootball" in s:
        return "NFL"
    if "college" in s or "ncaa" in s or "ncaaf" in s or "collegefootball" in s:
        return "NCAA"
    if "nba" in s or "basketball" in s:
        return "NBA"
    if "mlb" in s or "baseball" in s:
        return "MLB"
    if "nhl" in s or "icehockey" in s or "hockey" in s:
        return "NHL"
    return s.upper()

@app.route("/")
def index():
    csv_path = find_latest_prediction_csv()
    if not csv_path:
        return render_template_string(TEMPLATE, rows=[], sport_options=[], selected_sport="All", top5=False, updated_at="No data")

    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        return f"Error reading CSV: {e}", 500

    # column candidates
    sport_col = find_col(df, ["sport","Sport","category","league"])
    team1_col = find_col(df, ["team1","home","home_team","team_a","team1_name","home_team_name"])
    team2_col = find_col(df, ["team2","away","away_team","team_b","team2_name","away_team_name"])
    gametime_col = find_col(df, ["gametime","game_time","datetime","date","start","kickoff","start_time"])
    pick_col = find_col(df, ["pick","Pick","moneylinepick","ml_pick","predicted_winner","pick_team","selected","our_pick"])
    conf_col = find_col(df, ["confidence","Confidence","confidence_percent","conf","confidence(%)"])
    edge_col = find_col(df, ["edge","Edge","model_edge"])
    lock_col = find_col(df, ["lock","is_lock","lockemoji","lock_emoji"])
    upset_col = find_col(df, ["upset","is_upset","upsetemoji","upset_emoji","underdog"])
    ml_col = find_col(df, ["ml","moneyline","moneyline_home","moneyline_away","home_ml","away_ml"])
    ats_col = find_col(df, ["ats","spread","line","against_the_spread"])
    ou_col = find_col(df, ["ou","overunder","total","o/u","over_under"])
    reason_col = find_col(df, ["reason","Reason","explanation","Model vs Market","model_reason"])

    rows = []
    for _, r in df.iterrows():
        t1 = r[team1_col] if team1_col and team1_col in df.columns else r.get("Team1") or ""
        t2 = r[team2_col] if team2_col and team2_col in df.columns else r.get("Team2") or ""
        title = f"{t1} vs {t2}".strip()

        gametime = ""
        if gametime_col and gametime_col in df.columns:
            val = r[gametime_col]
            gametime = "" if pd.isna(val) else str(val)

        pick = "N/A"
        if pick_col and pick_col in df.columns:
            val = r[pick_col]
            if pd.notna(val) and str(val).strip() != "":
                pick = str(val).strip()

        conf_val = None
        if conf_col and conf_col in df.columns:
            conf_val = parse_percentish(r[conf_col])
        conf_display = "0.0%" if conf_val is None else f"{round(conf_val,1)}%"

        edge_val = None
        if edge_col and edge_col in df.columns:
            edge_val = parse_percentish(r[edge_col])
        edge_display = "N/A" if edge_val is None else f"{round(edge_val,1)}%"

        lock = False
        if lock_col and lock_col in df.columns:
            v = r[lock_col]
            lock = bool(v) and str(v).strip().lower() not in ("", "0", "false", "none", "nan")
        else:
            if edge_val is not None and edge_val >= 5.0:
                lock = True

        upset = False
        if upset_col and upset_col in df.columns:
            v = r[upset_col]
            upset = bool(v) and str(v).strip().lower() not in ("", "0", "false", "none", "nan")
        else:
            ml_try = None
            if ml_col and ml_col in df.columns:
                ml_try = r[ml_col]
                ml_num = parse_moneyline_numeric(ml_try)
                if ml_num is not None and ml_num > 0:
                    upset = True

        ml_display = "N/A"
        if ml_col and ml_col in df.columns:
            v = r[ml_col]
            ml_display = str(v) if pd.notna(v) else "N/A"
        else:
            h = find_col(df, ["home_ml","home moneyline","home_ml_value"])
            a = find_col(df, ["away_ml","away moneyline","away_ml_value"])
            if h and a:
                hv = r[h] if pd.notna(r[h]) else ""
                av = r[a] if pd.notna(r[a]) else ""
                ml_display = f"{hv} / {av}" if hv or av else "N/A"

        ats_display = "N/A"
        if ats_col and ats_col in df.columns:
            v = r[ats_col]
            ats_display = str(v) if pd.notna(v) else "N/A"

        ou_display = "N/A"
        if ou_col and ou_col in df.columns:
            v = r[ou_col]
            ou_display = str(v) if pd.notna(v) else "N/A"

        reason = ""
        if reason_col and reason_col in df.columns:
            reason = str(r[reason_col]) if pd.notna(r[reason_col]) else ""
        if not reason:
            reason = "Model vs Market probability differential"

        sport_raw = r[sport_col] if sport_col and sport_col in df.columns else r.get("league") or ""
        sport = normalize_sport_name(sport_raw)

        rows.append({
            "sport": sport,
            "title": title,
            "gametime": gametime,
            "pick": pick,
            "confidence": conf_display,
            "edge": edge_display,
            "edge_val": edge_val if edge_val is not None else 0.0,
            "lock": lock,
            "upset": upset,
            "ml": ml_display,
            "ats": ats_display,
            "ou": ou_display,
            "reason": reason
        })

    seen = sorted({r["sport"] for r in rows if r["sport"]})
    preferred = ["NFL","NCAA","NBA","NHL","MLB"]
    sport_options = [p for p in preferred if p in seen] + [s for s in seen if s not in preferred]

    selected_sport = (request.args.get("sport") or "All")
    top5_flag = request.args.get("top5","0") in ("1","true","True")

    filtered = [r for r in rows if selected_sport in ("All","") or r["sport"].strip().lower() == selected_sport.strip().lower()]

    filtered_sorted = sorted(filtered, key=lambda x: x.get("edge_val",0.0), reverse=True)

    if top5_flag:
        filtered_sorted = filtered_sorted[:5]

    try:
        mt = os.path.getmtime(find_latest_prediction_csv())
        updated_at = datetime.datetime.utcfromtimestamp(mt).strftime("%Y-%m-%d %H:%M UTC")
    except:
        updated_at = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    return render_template_string(TEMPLATE,
                                 rows=filtered_sorted,
                                 sport_options=sport_options,
                                 selected_sport=selected_sport,
                                 top5=top5_flag,
                                 updated_at=updated_at)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)), debug=False)
