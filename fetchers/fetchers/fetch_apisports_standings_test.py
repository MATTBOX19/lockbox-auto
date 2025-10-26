import os, requests, pandas as pd
from datetime import datetime

API_KEY = os.getenv("APISPORTS_KEY")
if not API_KEY:
    raise EnvironmentError("Missing $APISPORTS_KEY")

HEADERS = {"x-apisports-key": API_KEY}

TEST_ENDPOINTS = {
    "nfl_standings": "https://v1.american-football.api-sports.io/standings?league=1&season=2024",
    "nfl_games": "https://v1.american-football.api-sports.io/games?league=1&season=2024",
    "ncaaf_standings": "https://v1.american-football.api-sports.io/standings?league=2&season=2024",
    "ncaaf_games": "https://v1.american-football.api-sports.io/games?league=2&season=2024",
}

def fetch_and_preview(name, url):
    print(f"▶ {name}")
    r = requests.get(url, headers=HEADERS, timeout=30)
    data = r.json()
    print(f"  results={data.get('results')}, keys={list(data.keys())}")
    if "response" in data and data["response"]:
        sample = data["response"][0]
        print("  sample keys:", list(sample.keys())[:10])
    else:
        print("  ❌ no data")
    return data

def main():
    for name, url in TEST_ENDPOINTS.items():
        try:
            fetch_and_preview(name, url)
        except Exception as e:
            print(f"  ⚠️ {name} failed: {e}")

if __name__ == "__main__":
    main()
