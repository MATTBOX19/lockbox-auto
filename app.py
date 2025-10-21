import os
import pandas as pd
from flask import Flask, render_template_string
from datetime import datetime
from pathlib import Path

app = Flask(__name__)

# === HTML TEMPLATE (dark layout, same as before) ===
HTML_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>LockBox AI Picks</title>
<style>
  :root {
    --bg:#0d1117; --card:#0f1720; --muted:#9aa6b2; --accent:#1fb6ff; --gold:#ffd24a;
  }
  body {margin:0;font-family:Inter,system-ui,Segoe UI,Arial,sans-serif;background:var(--bg);color:#e6eef6;padding:28px;}
  .container {max-width:1200px;margin:0 auto;}
  header {text-align:center;margin-bottom:18px;}
  .brand {font-weight:800;color:var(--accent);font-size:28px}
  .subtitle {color:var(--muted);margin-top:6px}
  .cards {display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:14px;}
  .card {background:var(--card);padding:14px;border-radius:10px;border:1px solid rgba(255,255,255,0.05);
         box-shadow:0 6px 18px rgba(0,0,0,0.6);}
  .card h3 {margin:0 0 6px 0;font-size:16px;color:var(--accent)}
  .small {font-size:13px;color:var(--muted)}
  .pick {color:var(--gold);font-weight:700;margin-bottom:6px}
  .reason {margin-top:8px;color:#c9d6de;font-size:13px;opacity:0.9}
</style>
</head>
<body>
<div class="container">
  <header>
    <div class="brand">🔥 LockBox AI Picks 🔒</div>
    <div class="subtitle">Your edge, every game — Updated: {{ timestamp }}</div>
  </header>
  <div class="cards">
  {% for r in records %}
    <div class="card">
      <h3>{{ r['Title'] }}</h3>
      <div class="small">{{ r['GameTime'] }}</div>
      <div class="pick">Pick: {{ r['Pick'] }}</div>
      <div class="small">Confidence: {{ r['ConfidenceDisplay'] }} | Edge: {{ r['EdgeDisplay'] }}</div>
      <div class="reason">{{ r['Reason'] }}</div>
    </div>
  {% endfor %}
  </div>
</div>
</body>
</html>
"""

# === Load latest CSV ===
def load_predictions():
    out_dir = Path("Output")
    if out_dir.exists():
        files = sorted(out_dir.glob("Predictions_*_Explained.csv"))
        if files:
            latest = files[-1]
        else:
            latest = Path("predictions.csv")
    else:
        latest = Path("predictions.csv")

    if not latest.exists():
        return [], None

    df = pd.read_csv(latest, dtype=str, keep_default_na=False)
    records = []
    for _, row in df.iterrows():
        rec = {
            "Title": f"{row.get('Team1','')} vs {row.get('Team2','')}",
            "GameTime": row.get("GameTime",""),
            "Pick": row.get("MoneylinePick",""),
            "ConfidenceDisplay": row.get("Confidence(%)",""),
            "EdgeDisplay": row.get("Edge",""),
            "Reason": row.get("Reason","")
        }
        records.append(rec)
    return records, latest

@app.route("/")
def index():
    records, used_file = load_predictions()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    return render_template_string(HTML_TEMPLATE, records=records, timestamp=timestamp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)