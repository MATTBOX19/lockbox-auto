#!/usr/bin/env python3
"""
lockbox_dashboard.py

Phase 8: LockBox Live Dashboard Integration

Purpose:
  - Extends the web interface (Flask) to show current model metrics
  - Displays rolling performance data from /Output/metrics.json
  - Adds auto-refresh and summary section below picks grid
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
PRED_FILE = sorted(OUT_DIR.glob("Predictions_*_Explained.csv"))[-1] if list(OUT_DIR.glob("Predictions_*_Explained.csv")) else None

TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>🔥 LockBox AI Dashboard 🔒</title>
<meta http-equiv="refresh" content="60"> <!-- Auto-refresh every 60s -->
<style>
  body { background:#0d1117; color:#c9d1d9; font-family:Arial, sans-serif; margin:0; padding:0; }
  h1 { color:#58a6ff; text-align:center; padding:20px 0; }
  h2 { color:#e3b341; text-align:center; margin-top:10px; }
  table { width:90%; margin:auto; border-collapse:collapse; margin-top:20px; }
  th, td { border:1px solid #30363d; padding:8px 10px; text-align:center; }
  th { background:#161b22; color:#79c0ff; }
  .footer { color:#8b949e; font-size:0.85rem; text-align:center; margin:20px; }
</style>
</head>
<body>
  <h1>🔥 LockBox AI Dashboard 🔒</h1>
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

def load_metrics():
    if METRICS_FILE.exists():
        try:
            with open(METRICS_FILE) as f:
                metrics = json.load(f)
                if isinstance(metrics, list):
                    return list(reversed(metrics[-10:]))  # last 10 sessions
        except Exception as e:
            print(f"Error loading metrics: {e}")
    return []

@app.route("/")
def dashboard():
    metrics = load_metrics()
    if PRED_FILE and PRED_FILE.exists():
        df = pd.read_csv(PRED_FILE)
        data = df.to_dict(orient="records")
        updated = PRED_FILE.name
    else:
        data, updated = None, "N/A"

    return render_template_string(TEMPLATE, metrics=metrics, data=data, updated=updated)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10001)
