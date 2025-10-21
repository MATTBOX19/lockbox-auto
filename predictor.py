import os, math, requests, pandas as pd
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ======= CONFIG =======
API_KEY = os.getenv("ODDS_API_KEY")
SPORTS = ["americanfootball_nfl", "basketball_nba", "icehockey_nhl", "baseball_mlb"]
REGION = "us"
MARKETS = "h2h,spreads,totals"
ODDS_API_URL = "https://api.the-odds-api.com/v4/sports/{sport}/odds"

# ======= FUNCTIONS =======
def implied_prob(odds):
    try:
        odds = float(odds)
        return 100 / (odds + 100) if odds > 0 else abs(odds) / (abs(odds) + 100)
    except:
        return None

def calculate_edge(model_prob, market_prob):
    if model_prob is None or market_prob is None:
        return None
    return round((model_prob - market_prob) * 100, 2)

def emoji_for_pick(lock=False, upset=False):
    if lock:
        return "🔒"
    elif upset:
        return "🚨"
    return ""

# ======= MODEL PREDICTOR =======
def run_predictor():
    all_rows = []
    out_dir = Path("Output")
    out_dir.mkdir(exist_ok=True)

    for sport in SPORTS:
        url = ODDS_API_URL.format(sport=sport)
        r = requests.get(url, params={"apiKey": API_KEY, "regions": REGION, "markets": MARKETS})
        if r.status_code != 200:
            print(f"⚠️ Error fetching {sport}: {r.status_code}")
            continue

        games = r.json()
        for g in games:
            try:
                team1, team2 = g["home_team"], g["away_team"]
                commence = g["commence_time"]

                # Extract Moneyline odds
                h2h = g["bookmakers"][0]["markets"][0]["outcomes"]
                home_odds = next((o["price"] for o in h2h if o["name"] == team1), None)
                away_odds = next((o["price"] for o in h2h if o["name"] == team2), None)

                home_prob = implied_prob(home_odds)
                away_prob = implied_prob(away_odds)

                # --- Basic predictor (random placeholder logic until full model reinstated)
                model_home_prob = home_prob + 0.03 if home_prob else 0.52
                edge = calculate_edge(model_home_prob, home_prob)

                lock = edge and edge > 6
                upset = away_prob and away_prob < 0.40 and model_home_prob < 0.50

                all_rows.append({
                    "Sport": sport,
                    "GameTime": commence,
                    "Team1": team2,
                    "Team2": team1,
                    "MoneylinePick": team1 if model_home_prob > 0.5 else team2,
                    "Confidence(%)": round(model_home_prob * 100, 1),
                    "Edge": f"{edge}%",
                    "LockEmoji": "🔒" if lock else "",
                    "UpsetEmoji": "🚨" if upset else "",
                    "Reason": "Model vs Market probability differential",
                })
            except Exception as e:
                print(f"Error parsing game: {e}")

    df = pd.DataFrame(all_rows)
    out_file = out_dir / f"Predictions_{datetime.now().strftime('%Y-%m-%d')}_Explained.csv"
    df.to_csv(out_file, index=False)
    print(f"✅ Saved {out_file}")

if __name__ == "__main__":
    run_predictor()
