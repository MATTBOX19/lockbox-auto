# app.py -- minimal Flask dashboard that reads the latest Predictions_*_Explained.csv
# and renders cards with Pick, Lock/Alert emoji, Confidence, Edge, ML/ATS odds, Total.
# Paste this file as-is into your repo root.

from flask import Flask, render_template_string
import pandas as pd
from pathlib import Path
from datetime import datetime
import os

app = Flask(__name__)

HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>LockBox AI Picks</title>
<style>
  :root{--bg:#0d1117;--card:#0f1720;--muted:#9aa6b2;--accent:#1fb6ff;--gold:#ffd24a}
  body{margin:0;font-family:Inter,system-ui,Segoe UI,Arial,sans-serif;background:var(--bg);color:#e6eef6;padding:24px}
  .container{max-width:1200px;margin:0 auto}
  .brand{font-weight:800;color:var(--accent);font-size:26px;text-align:center}
  .subtitle{text-align:center;color:var(--muted);margin-bottom:18px}
  .cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:14px}
  .card{background:var(--card);padding:14px;border-radius:10px;border:1px solid rgba(255,255,255,0.03);min-height:140px}
  .card h3{margin:0 0 8px 0;color:var(--accent);font-size:16px}
  .meta{color:var(--muted);font-size:13px;margin-bottom:8px}
  .pick{color:var(--gold);font-weight:700;margin-bottom:8px}
  .small{font-size:13px;color:var(--muted)}
  .sport-chip{font-weight:700;color:#fff;font-size:12px;padding:6px 8px;border-radius:8px;float:right}
  .sport-nfl{background:#052b12}.sport-ncaa{background:#352b05}.sport-nba{background:#2b0529}.sport-mlb{background:#05223a}.sport-nhl{background:#11111a}
  @media(max-width:720px){ .cards{grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:12px} }
</style>
</head>
<body>
  <div class="container">
    <div class="brand">🔥 LockBox AI Picks 🔐</div>
    <div class="subtitle">Updated: {{ timestamp }}</div>

    <div class="cards">
      {% for r in records %}
      <article class="card" data-sport="{{ r['Sport'] }}" data-confidence="{{ r['ConfidenceNum'] }}">
        <h3>{{ r['Title'] }}</h3>
        <div class="meta">
          <span class="small">{{ r['GameTimeDisplay'] }}</span>
          <div style="float:right"><span class="sport-chip sport-{{ r['Sport']|lower }}">{{ r['Sport'] }}</span></div>
        </div>

        <div class="small">Home ML: {{ r['HomeML'] or '' }} &nbsp; Away ML: {{ r['AwayML'] or '' }}</div>
        <div class="pick">
          Pick: {{ r['Pick'] or '' }}
          {% if r['RecordsRaw'].get('LockEmoji') %} {{ r['RecordsRaw'].get('LockEmoji') }}{% elif r['Lock'] %} 🔒{% endif %}
          {% if r['RecordsRaw'].get('UpsetEmoji') %} {{ r['RecordsRaw'].get('UpsetEmoji') }}{% endif %}
        </div>

        <div class="small">
          Model: {{ r['AdjustedConfidenceDisplay'] or r['ConfidenceDisplay'] or r['RecordsRaw'].get('Confidence(%)','')|default('') }}
          &nbsp; Edge: {{ r['Edge'] or r['RecordsRaw'].get('Edge','') or '' }}
          {% if r['RecordsRaw'].get('ML_Odds') %} &nbsp; ML Odds: {{ r['RecordsRaw'].get('ML_Odds') }}{% endif %}
          {% if r['RecordsRaw'].get('ATS_Odds') %} &nbsp; ATS Odds: {{ r['RecordsRaw'].get('ATS_Odds') }}{% endif %}
          {% if r['RecordsRaw'].get('TotalPick') %} &nbsp; Total: {{ r['RecordsRaw'].get('TotalPick') }}{% endif %}
        </div>

        <div class="small" style="margin-top:8px;color:#c9d6de">{{ r['Reason'] or '' }}</div>
      </article>
      {% endfor %}
    </div>
  </div>
</body>
</html>
"""

def find_latest_predictions():
    out = Path("Output")
    if out.exists():
        files = sorted(out.glob("Predictions_*_Explained.csv"))
        if files:
            return files[-1]
    # fallback to predictions.csv in repo root
    p = Path.cwd() / "predictions.csv"
    return p if p.exists() else None

def read_records():
    f = find_latest_predictions()
    if not f:
        return [], None
    # read with utf-8-sig to strip BOM if present; keep_default_na=False so blanks are ""
    try:
        df = pd.read_csv(f, encoding='utf-8-sig', dtype=str, keep_default_na=False)
    except Exception:
        # fallback - let pandas infer
        df = pd.read_csv(f, dtype=str, keep_default_na=False)
    # normalize column names: older files may have "Confidence(%)" or "Confidence_pct" etc.
    records = []
    for _, row in df.fillna("").iterrows():
        rec_raw = row.to_dict()
        # pick confidence numeric: check several variants
        conf_val = ""
        for k in ("AdjustedConfidence","Confidence","Confidence(%)","Confidence_pct","Confidence_pct"):
            if k in rec_raw and str(rec_raw.get(k) or "").strip() != "":
                conf_val = rec_raw.get(k)
                break
        try:
            conf_num = float(conf_val) if conf_val != "" else 0.0
        except Exception:
            conf_num = 0.0

        adjusted_display = ""
        try:
            if rec_raw.get("AdjustedConfidence") not in (None,""):
                adjusted_display = f"{round(float(rec_raw.get('AdjustedConfidence')) ,1)}%"
        except Exception:
            adjusted_display = ""

        confidence_display = ""
        try:
            if rec_raw.get("Confidence") not in (None,""):
                confidence_display = f"{round(float(rec_raw.get('Confidence')) ,1)}%"
            elif rec_raw.get("Confidence(%)") not in (None,""):
                confidence_display = f"{round(float(rec_raw.get('Confidence(%)')) ,1)}%"
        except Exception:
            confidence_display = ""

        # normalize emoji fields; ensure strings
        rec_raw["LockEmoji"] = rec_raw.get("LockEmoji") or ""
        rec_raw["UpsetEmoji"] = rec_raw.get("UpsetEmoji") or ""

        # derive sport label/class
        sport_raw = (rec_raw.get("Sport") or "").strip()
        sport_class = (sport_raw or "").upper()
        if sport_class.lower() in ["americanfootball"]:
            # keep it as NFL/NCAA depending on your upstream mapping; simple heuristic: leave as-is
            sport_class = sport_class

        rec = {
            "Title": f"{rec_raw.get('Team1','')} @ {rec_raw.get('Team2','')}",
            "GameTimeDisplay": rec_raw.get("GameTime",""),
            "Team1": rec_raw.get("Team1",""),
            "Team2": rec_raw.get("Team2",""),
            "HomeML": rec_raw.get("MoneylinePick","") or rec_raw.get("HomeML",""),
            "AwayML": rec_raw.get("AwayML",""),
            "Pick": (rec_raw.get("MoneylinePick") or rec_raw.get("ATSPick") or ""),
            "Confidence": rec_raw.get("Confidence",""),
            "AdjustedConfidence": rec_raw.get("AdjustedConfidence",""),
            "AdjustedConfidenceDisplay": adjusted_display,
            "ConfidenceDisplay": confidence_display,
            "Edge": rec_raw.get("Edge",""),
            "Reason": rec_raw.get("Reason",""),
            "SportLabel": rec_raw.get("SportLabel",""),
            "Sport": sport_class or (rec_raw.get("RowClass","").upper() or ""),
            "Lock": bool(rec_raw.get("Lock") in ("True","true","TRUE",True)) or (conf_num >= 80),
            "RecordsRaw": rec_raw,
            "ConfidenceNum": conf_num
        }
        # if LockEmoji present, treat as lock
        if rec["RecordsRaw"].get("LockEmoji"):
            rec["Lock"] = True

        records.append(rec)
    return records, f

@app.route("/")
def index():
    try:
        records, used = read_records()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        return render_template_string(HTML, records=records, timestamp=timestamp)
    except Exception as e:
        return f"<pre>⚠️ Error rendering dashboard: {e}</pre>"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
