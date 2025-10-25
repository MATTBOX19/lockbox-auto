import csv, datetime as dt, time, requests
from collections import defaultdict

BASE = "https://api.balldontlie.io/v1"

def fetch_team_stats(season=2024):
    team_stats = defaultdict(lambda: defaultdict(float))
    per_team_games = defaultdict(int)
    page = 1
    while True:
        url = f"{BASE}/games?seasons[]={season}&per_page=100&page={page}"
        r = requests.get(url, timeout=15)
        data = r.json()
        games = data.get("data", [])
        if not games:
            break
        for g in games:
            for side in ("home_team", "visitor_team"):
                t = g[side]
                tid, team_name = t["id"], t["abbreviation"]
                pts = g["home_team_score"] if side == "home_team" else g["visitor_team_score"]
                opp_pts = g["visitor_team_score"] if side == "home_team" else g["home_team_score"]
                team_stats[team_name]["points_for"] += pts
                team_stats[team_name]["points_against"] += opp_pts
                per_team_games[team_name] += 1
        page += 1
        time.sleep(0.1)

    rows = []
    now = dt.datetime.utcnow().isoformat() + "Z"
    for team, s in team_stats.items():
        gp = per_team_games[team]
        rows.append({
            "sport": "NBA",
            "team": team,
            "games_played": gp,
            "points_for": round(s["points_for"], 1),
            "points_against": round(s["points_against"], 1),
            "updated_at": now
        })
    return rows

def write_csv(rows, path):
    if not rows: return
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader(); w.writerows(rows)

if __name__ == "__main__":
    rows = fetch_team_stats()
    write_csv(rows, "Data/nba_team_stats_free.csv")
    print(f"Saved NBA: {len(rows)} rows → Data/nba_team_stats_free.csv")
