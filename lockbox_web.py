# lockbox_web.py
#
# Flask app to show LockBox predictions with:
# - sport dropdown (All / NFL / NCAA / NBA / NHL / MLB + any found in CSV)
# - Top 5 toggle (by Edge)
# - Lock emoji (🔒), Upset (🚨), Confidence(%) and Edge(%)
# - Moneyline (ML), ATS and O/U if present in CSV (otherwise shows N/A)
#
# Requirements: Flask, pandas
# Place this file in your repo root (same place you run the web service).
# The app will look for the latest CSV under Output/Predictions_*.csv

from flask import Flask, request, render_template_string, abort
import pandas as pd
import glob
import os
import datetime

app = Flask(__name__)

# HTML template embedded: dark theme cards, dropdown + top5 toggle
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
      --accent-dark:#083141;
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
            <option value="All Games" {% if selected_sport=='All Games' %}selected{% endif %}>All Games</option>
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

          <div class="pick">{{ r.pick }} 
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
    # look for Output/Predictions_*.csv (common name from your existing script)
    patterns = [
        "Output/Predictions_*.csv",
        "Output/*.csv",
        "Predictions_*.csv",
        "Output/Predictions_*.CSV"
    ]
    candidates = []
    for p in patterns:
        candidates.extend(glob.glob(p))
    if not candidates:
        return None
    # pick newest by modified time
    candidates = sorted(candidates, key=lambda x: os.path.getmtime(x), reverse=True)
    return candidates[0]

def find_col(df, candidates):
    # find first matching column name case-insensitively
    cols = {c.lower(): c for c in df.columns}
    for cand in candidates:
        cand_l = cand.lower()
        if cand_l in cols:
            return cols[cand_l]
    # try contains match
    for cand in candidates:
        for c in df.columns:
            if cand.lower() in c.lower():
                return c
    return None

@app.route("/")
def index():
    csv_path = find_latest_prediction_csv()
    if not csv_path:
        return render_template_string(TEMPLATE, rows=[], sport_options=[], selected_sport="All Games", top5=False, updated_at="No data")
    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        return f"Error reading CSV: {e}", 500

    # normalize/lookup columns
    sport_col = find_col(df, ["sport", "Sport"])
    team1_col = find_col(df, ["team1", "home", "home_team", "team_a", "team1_name"])
    team2_col = find_col(df, ["team2", "away", "away_team", "team_b", "team2_name"])
    gametime_col = find_col(df, ["gametime", "GameTime", "game_time", "datetime", "date"])
    pick_col = find_col(df, ["moneylinepick", "pick", "MoneylinePick", "ml_pick", "pick_team"])
    conf_col = find_col(df, ["confidence(%)", "confidence", "Confidence", "confidence_percent", "conf"])
    edge_col = find_col(df, ["edge", "Edge"])
    lock_col = find_col(df, ["lockemoji", "lock", "is_lock", "lock_emoji"])
    upset_col = find_col(df, ["upsetemoji", "upset", "is_upset", "upset_emoji"])
    ml_col = find_col(df, ["ml", "moneyline", "moneyline_home", "home_ml", "away_ml"])
    ats_col = find_col(df, ["ats", "spread", "line", "against_the_spread"])
    ou_col = find_col(df, ["ou", "overunder", "total", "o/u", "over_under"])
    reason_col = find_col(df, ["reason", "Reason", "Model vs Market", "explanation"])

    # Build display rows
    rows = []
    for _, r in df.iterrows():
        sport = r[sport_col] if sport_col and sport_col in df.columns else "Unknown"
        team1 = r[team1_col] if team1_col and team1_col in df.columns else (r.get("Team1") or "")
        team2 = r[team2_col] if team2_col and team2_col in df.columns else (r.get("Team2") or "")
        title = f"{team1} vs {team2}".strip()
        gametime = ""
        if gametime_col and gametime_col in df.columns:
            try:
                val = r[gametime_col]
                if pd.isna(val):
                    gametime = ""
                else:
                    # try parse or just show value
                    gametime = str(val)
            except Exception:
                gametime = ""
        pick = ""
        if pick_col and pick_col in df.columns:
            pick = r[pick_col]
        else:
            pick = str(r.get("Pick") or r.get("moneylinepick") or "")

        # confidence formatting
        confidence = r[conf_col] if conf_col and conf_col in df.columns else r.get("Confidence") or r.get("confidence") or ""
        try:
            if pd.notna(confidence) and confidence != "":
                confidence = float(confidence)
                confidence = f"{round(confidence,1)}%"
            else:
                confidence = "N/A"
        except Exception:
            confidence = str(confidence)

        # edge formatting
        edge = r[edge_col] if edge_col and edge_col in df.columns else r.get("Edge") or ""
        try:
            if pd.notna(edge) and edge != "":
                edge = float(edge)
                # if already like 3 or 3.0 -> show with % suffix
                edge = f"{round(edge,1)}%"
            else:
                edge = "N/A"
        except Exception:
            edge = str(edge)

        lock = False
        if lock_col and lock_col in df.columns:
            val = r[lock_col]
            lock = bool(val) and str(val).strip() not in ["", "0", "False", "false", "None", "nan"]
        else:
            # fallback: if Edge large enough consider lock? keep False
            lock = False

        upset = False
        if upset_col and upset_col in df.columns:
            val = r[upset_col]
            upset = bool(val) and str(val).strip() not in ["", "0", "False", "false", "None", "nan"]

        # ml / ats / ou
        ml = "N/A"
        if ml_col and ml_col in df.columns:
            ml_v = r[ml_col]
            ml = str(ml_v) if pd.notna(ml_v) else "N/A"
        else:
            # if columns like Home ML and Away ML exist, show "home:val / away:val" condense
            home_ml = find_col(df, ["home_ml", "home moneyline", "home_ml_value"])
            away_ml = find_col(df, ["away_ml", "away moneyline", "away_ml_value"])
            if home_ml and away_ml:
                ml = f"{r[home_ml] if pd.notna(r[home_ml]) else ''} / {r[away_ml] if pd.notna(r[away_ml]) else ''}"

        ats = "N/A"
        if ats_col and ats_col in df.columns:
            ats = str(r[ats_col]) if pd.notna(r[ats_col]) else "N/A"

        ou = "N/A"
        if ou_col and ou_col in df.columns:
            ou = str(r[ou_col]) if pd.notna(r[ou_col]) else "N/A"

        reason = ""
        if reason_col and reason_col in df.columns:
            reason = str(r[reason_col]) if pd.notna(r[reason_col]) else ""
        else:
            reason = "Model vs Market probability differential"

        rows.append({
            "sport": str(sport),
            "title": title,
            "gametime": gametime,
            "pick": str(pick),
            "confidence": confidence,
            "edge": edge,
            "lock": lock,
            "upset": upset,
            "ml": ml,
            "ats": ats,
            "ou": ou,
            "reason": reason
        })

    # unique sport options: prefer common order, but include any seen sports
    seen_sports = sorted({r["sport"] for r in rows if r["sport"] and str(r["sport"]).strip()})
    # prefer the list in requested order
    preferred = ["NFL", "NCAA", "NBA", "NHL", "MLB"]
    sport_options = []
    for p in preferred:
        if p in seen_sports:
            sport_options.append(p)
    for s in seen_sports:
        if s not in sport_options:
            sport_options.append(s)

    # query params
    selected_sport = (request.args.get("sport") or "All Games")
    top5 = request.args.get("top5", "0") in ["1", "true", "True"]

    # filter rows
    filtered = []
    for r in rows:
        if selected_sport and selected_sport != "All Games":
            if str(r["sport"]).strip().lower() != selected_sport.strip().lower():
                continue
        filtered.append(r)

    # sort by edge numeric if possible; otherwise keep order
    def edge_key(item):
        try:
            # remove trailing % if present
            e = str(item.get("edge","")).replace("%","")
            return float(e)
        except Exception:
            return 0.0
    filtered_sorted = sorted(filtered, key=edge_key, reverse=True)

    if top5:
        filtered_sorted = filtered_sorted[:5]

    updated_at = ""
    try:
        mt = os.path.getmtime(csv_path)
        updated_at = datetime.datetime.utcfromtimestamp(mt).strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        updated_at = datetime.datetime.utcnow().isoformat()

    return render_template_string(TEMPLATE,
                                  rows=filtered_sorted,
                                  sport_options=sport_options,
                                  selected_sport=selected_sport,
                                  top5=top5,
                                  updated_at=updated_at)

if __name__ == "__main__":
    # for local dev: run with `python lockbox_web.py`
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)), debug=False)
