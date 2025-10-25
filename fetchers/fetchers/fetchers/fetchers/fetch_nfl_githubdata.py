import pandas as pd, datetime as dt, csv

URL = "https://raw.githubusercontent.com/nflverse/nflfastR-data/master/data/games.csv.gz"

def fetch_team_stats():
    df = pd.read_csv(URL, compression="gzip")
    recent = df[df["season"] >= 2023]
    team_stats = (
        recent.groupby("home_team")[["home_score", "away_score"]]
        .sum()
        .rename(columns={"home_score": "points_for", "away_score": "points_against"})
    )
    team_stats["games_played"] = recent.groupby("home_team").size().values
    team_stats.reset_index(inplace=True)
    now = dt.datetime.utcnow().isoformat() + "Z"
    team_stats["sport"] = "NFL"
    team_stats["updated_at"] = now
    return team_stats.to_dict(orient="records")

def write_csv(rows, path):
    if not rows: return
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader(); w.writerows(rows)

if __name__ == "__main__":
    rows = fetch_team_stats()
    write_csv(rows, "Data/nfl_team_stats_free.csv")
    print(f"Saved NFL: {len(rows)} rows → Data/nfl_team_stats_free.csv")
