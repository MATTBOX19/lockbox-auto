from flask import Flask, render_template_string
import pandas as pd
from pathlib import Path

app = Flask(__name__)

TEMPLATE = """
<!doctype html>
<html>
<head>
<meta charset="utf-8"/>
<title>LockBox AI Picks</title>
<style>
body{background:#0d1117;color:#e6eef6;font-family:system-ui;margin:0;padding:28px;}
.container{max-width:1200px;margin:auto;}
.brand{color:#1fb6ff;font-weight:800;font-size:28px;text-align:center;}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:14px;}
.card{background:#0f1720;padding:14px;border-radius:10px;box-shadow:0 6px 18px rgba(0,0,0,.6);}
.pick{color:#ffd24a;font-weight:700;margin-bottom:8px}
.meta{font-size:13px;color:#9aa6b2;margin-bottom:6px}
.lock{color:#f6c84c} .upset{color:#ff5c5c}
</style>
</head>
<body>
<div class="container">
  <div class="brand">🔥 LockBox AI Top 5 Picks 🔥</div>
  {% for g in top %}
  <div class="card">
    <div class="meta">{{g.Sport}} | {{g.GameTime}}</div>
    <div class="pick">{{g.MoneylinePick}} {{g.LockEmoji}}{{g.UpsetEmoji}}</div>
    <div>Confidence: {{g['Confidence(%)']}} %  | Edge: {{g.Edge}}</div>
  </div>
  {% endfor %}
</div>
</body>
</html>
"""

@app.route("/")
def index():
    out = Path("Output")
    files = sorted(out.glob("Predictions_*_Explained.csv")) if out.exists() else []
    f = files[-1] if files else None
    if not f:
        return "No predictions yet."
    df = pd.read_csv(f)
    df["Confidence(%)"] = pd.to_numeric(df["Confidence(%)"], errors="coerce").fillna(0)
    df["EdgeNum"] = pd.to_numeric(df["Edge"].str.replace("%",""), errors="coerce").fillna(0)
    df["Score"] = df["Confidence(%)"] * (1 + df["EdgeNum"]/100)
    top = df.sort_values("Score", ascending=False).head(5).to_dict(orient="records")
    return render_template_string(TEMPLATE, top=top)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
