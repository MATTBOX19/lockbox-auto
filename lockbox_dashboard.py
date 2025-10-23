#!/usr/bin/env python3
"""
lockbox_dashboard.py

LockBox Pro Dashboard
- Displays model metrics, per-sport performance, and current predictions.
"""

from flask import Flask, render_template_string
import pandas as pd
import json
from pathlib import Path
from datetime import datetime

app = Flask(__name__)

ROOT = Path(".")
OUT_DIR = ROOT / "Output"
METRICS_FILE = OUT_DIR / "metrics.json"
PERFORMANCE_FILE = OUT_DIR / "performance.json"
PRED_FILE = sorted(OUT_DIR.glob("Predictions_*_Explained.csv"))[-1] if list(OUT_DIR.glob("Predictions_*_Explained.csv")) else None

TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>🔥 LockBox AI Dashboard 🔒</title>
<meta http-equiv="refresh" content="60">
<style>
  body { background:#0d1117; color:#c9d1d9; font-family:Arial, sans-serif; margin:0; padding:0; }
  h1 { color:#58a6ff; text-align:center; padding:20px 0; }
  h2 { color:#e3b341; text-align:center; margin-top:10px; }
  table { width:90%; margin:auto; border-collapse:collapse; margin-top:20px; }
  th, td { border:1px solid #30363d; padding:8px 10px; text-align:center; }
  th { background:#161b22; color:#79c0ff; }
  .footer { color:#8b949e; font-size:0.85rem; text-align:center; margin:20px; }
  .sport-table th { background:#21262d; color:#ffa657; }
</style>
</head>
<body>
  <h1>🔥 LockBox AI Dashboard 🔒</h1>

  {% if perf %}
    <h2>Per-Sport Performance (Live)</h2>
    <table class="sport-table">
      <tr><th>Sport</th><th>ML Win%</th><th>ATS Win%</th><th>OU Win%</th><th>Avg ROI%</th></tr>
      {% for sport,vals in perf.items() %}
        {% if sport != "updated" %}
        <tr>
          <td>{{ sport }}</td>
          <td>{{ vals['ML']['win_pct'] if 'ML' in vals else '—' }}</td>
          <td>{{ vals['ATS']['win_pct'] if 'ATS' in vals else '—' }}</td>
          <td>{{ vals['OU']['win_pct'] if 'OU' in vals else '—' }}</td>
          <td>
            {{
              "%.1f"|format(
                (
                  (vals['ML'].get('roi',0) + vals['ATS'].get('roi',0) + vals['OU'].get('roi',0)
                  ) / 3.0
                ) if 'ML' in vals else 0
              )
            }}
          </td>
        </tr>
        {% endif %}
      {% endfor %}
    </table>
  {% else %}
    <p style="text-align:center;color:#8b949e;">No per-sport performance data available yet.</p>
  {% endif %}

  <h2>Model Performance Summary</h2>
  {% if metrics %}
    <table>
      <tr>
        <th>Date (UTC)</th><th>Win %</th><th>ROI %</th><th>Avg Edge</th><th>Avg Confidence</th><th>Games Settled</th>
      </tr>
      {% for m in metrics %}
      <tr>
        <td>{{ m.timestamp.split('T')[0] }}</td>
        <td>{{ m.win_pct }}</td>
        <td>{{ m.roi_percent }}</td>
        <td>{{ m.avg_edge }}</td>
        <td>{{ m.avg_confidence }}</td>
        <td>{{ m.games_settled }}</td>
      </tr>
      {% endfor %}
    </table>
  {% else %}
    <p style="text-align:center;color:#8b949e;">No metrics available yet. Run lockbox_learn.py first.</p>
  {% endif %}

  <h2>Current Predictions</h2>
  {% if data is not none %}
    <table>
      <tr>
        <th>Sport</th><th>Teams</th><th>Pick</th><th>Edge</th><th>Confidence</th><th>Reason</th>
      </tr>
      {% for row in data %}
      <tr>
        <td>{{ row.Sport }}</td>
        <td>{{ row.Team1 }} vs {{ row.Team2 }}</td>
        <td>{{ row.MoneylinePick }}</td>
        <td>{{ "%.2f"|format(row.Edge) }}</td>
        <td>{{ "%.1f"|format(row.Confidence) }}</td>
        <td>{{ row.Reason }}</td>
      </tr>
      {% endfor %}
    </table>
  {% else %}
    <p style="text-align:center;color:#8b949e;">No current predictions available.</p>
  {% endif %}

  <div class="footer">
    Updated: {{ updated }} | Auto-refresh every 60s
  </div>
</body>
</html>
"""

def load_json(path):
    if path.exists():
        try:
            with open(path) as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading {path.name}: {e}")
    return None

@app.route("/")
def dashboard():
    metrics = load_json(METRICS_FILE) or []
    perf = load_json(PERFORMANCE_FILE)
    if isinstance(metrics, list):
        metrics = list(reversed(metrics[-10:]))
    if PRED_FILE and PRED_FILE.exists():
        df = pd.read_csv(PRED_FILE)
        data = df.to_dict(orient="records")
        updated = PRED_FILE.name
    else:
        data, updated = None, "N/A"

    return render_template_string(TEMPLATE, metrics=metrics, perf=perf, data=data, updated=updated)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10001)
