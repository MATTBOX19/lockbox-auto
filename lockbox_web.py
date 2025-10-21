from flask import Flask, render_template_string
import os
import pandas as pd
from datetime import datetime

app = Flask(__name__)

# --- HTML template for displaying the predictions ---
TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LockBox Daily Predictions</title>
    <style>
        body {
            background-color: #0b0b0d;
            color: #e6e6e6;
            font-family: Arial, sans-serif;
            text-align: center;
            margin: 0;
            padding: 20px;
        }
        h1 {
            color: #00d4ff;
            margin-bottom: 10px;
        }
        h3 {
            color: #999;
            margin-top: 0;
        }
        table {
            width: 90%;
            margin: 20px auto;
            border-collapse: collapse;
            background-color: #151519;
            border-radius: 8px;
            overflow: hidden;
        }
        th, td {
            padding: 10px;
            border-bottom: 1px solid #222;
        }
        th {
            background-color: #1f1f25;
            color: #00d4ff;
        }
        tr:hover {
            background-color: #222;
        }
        .league {
            margin-top: 40px;
            color: #ff9900;
            text-transform: uppercase;
            border-bottom: 2px solid #ff9900;
            display: inline-block;
            padding-bottom: 4px;
        }
        .timestamp {
            font-size: 0.9em;
            color: #888;
            margin-top: 20px;
        }
    </style>
</head>
<body>
    <h1>🏈🏀 LockBox Daily Predictions 🏒⚾</h1>
    <h3>Automatically updated every 24 hours</h3>

    {% if predictions %}
        {% for league, games in predictions.items() %}
            <h2 class="league">{{ league }}</h2>
            <table>
                <tr>
                    {% for col in games.columns %}
                        <th>{{ col }}</th>
                    {% endfor %}
                </tr>
                {% for _, row in games.iterrows() %}
                <tr>
                    {% for val in row %}
                        <td>{{ val }}</td>
                    {% endfor %}
                </tr>
                {% endfor %}
            </table>
        {% endfor %}
    {% else %}
        <p>No prediction files found yet.</p>
    {% endif %}

    <div class="timestamp">
        {% if timestamp %}
            Last updated: {{ timestamp }}
        {% endif %}
    </div>
</body>
</html>
"""

def get_latest_prediction():
    """Find the newest predictions file in Output/."""
    output_dir = os.path.join(os.getcwd(), "Output")
    if not os.path.exists(output_dir):
        return None, None

    files = [f for f in os.listdir(output_dir) if f.endswith("_Explained.csv")]
    if not files:
        return None, None

    latest_file = max(files, key=lambda x: os.path.getmtime(os.path.join(output_dir, x)))
    timestamp = datetime.fromtimestamp(os.path.getmtime(os.path.join(output_dir, latest_file))).strftime("%Y-%m-%d %H:%M:%S")

    df = pd.read_csv(os.path.join(output_dir, latest_file))

    # Detect leagues from Team names or separate League column
    leagues = ["NFL", "NCAA", "NBA", "NHL", "MLB"]
    predictions = {}
    if "League" in df.columns:
        for lg in leagues:
            league_df = df[df["League"].str.contains(lg, case=False, na=False)]
            if not league_df.empty:
                predictions[lg] = league_df
    else:
        # fallback: split evenly by league name in team columns
        for lg in leagues:
            mask = df.apply(lambda x: x.astype(str).str.contains(lg, case=False)).any(axis=1)
            if mask.any():
                predictions[lg] = df[mask]

    return predictions, timestamp


@app.route("/")
def index():
    predictions, timestamp = get_latest_prediction()
    return render_template_string(TEMPLATE, predictions=predictions, timestamp=timestamp)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)