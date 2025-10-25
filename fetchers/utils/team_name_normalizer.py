import re

def normalize_team_name(name: str) -> str:
    """
    Standardize team names, abbreviations, and city variations across leagues.
    Used to make merging odds and stats consistent.
    """
    if not name:
        return ""
    name = name.strip().lower()

    replacements = {
        # NFL
        "washington commanders": "WAS",
        "washington football team": "WAS",
        "new england patriots": "NE",
        "buffalo bills": "BUF",
        "miami dolphins": "MIA",
        "new york jets": "NYJ",
        "baltimore ravens": "BAL",
        "cincinnati bengals": "CIN",
        "cleveland browns": "CLE",
        "pittsburgh steelers": "PIT",
        "houston texans": "HOU",
        "indianapolis colts": "IND",
        "jacksonville jaguars": "JAX",
        "tennessee titans": "TEN",
        "denver broncos": "DEN",
        "kansas city chiefs": "KC",
        "las vegas raiders": "LV",
        "los angeles chargers": "LAC",
        "dallas cowboys": "DAL",
        "new york giants": "NYG",
        "philadelphia eagles": "PHI",
        "washington redskins": "WAS",
        "san francisco 49ers": "SF",
        "seattle seahawks": "SEA",
        "green bay packers": "GB",
        "minnesota vikings": "MIN",
        "chicago bears": "CHI",
        "detroit lions": "DET",
        "new orleans saints": "NO",
        "atlanta falcons": "ATL",
        "carolina panthers": "CAR",
        "tampa bay buccaneers": "TB",
        "los angeles rams": "LAR",
        "arizona cardinals": "ARI",

        # NBA
        "los angeles lakers": "LAL",
        "los angeles clippers": "LAC",
        "golden state warriors": "GSW",
        "phoenix suns": "PHX",
        "sacramento kings": "SAC",
        "boston celtics": "BOS",
        "brooklyn nets": "BKN",
        "new york knicks": "NYK",
        "philadelphia 76ers": "PHI",
        "miami heat": "MIA",
        "milwaukee bucks": "MIL",
        "cleveland cavaliers": "CLE",
        "chicago bulls": "CHI",
        "detroit pistons": "DET",
        "atlanta hawks": "ATL",
        "washington wizards": "WAS",
        "toronto raptors": "TOR",
        "dallas mavericks": "DAL",
        "houston rockets": "HOU",
        "memphis grizzlies": "MEM",
        "new orleans pelicans": "NOP",
        "oklahoma city thunder": "OKC",
        "portland trail blazers": "POR",
        "utah jazz": "UTA",
        "denver nuggets": "DEN",
        "minnesota timberwolves": "MIN",
        "san antonio spurs": "SAS",
        "orlando magic": "ORL",
        "charlotte hornets": "CHA",
        "indiana pacers": "IND",

        # MLB
        "new york yankees": "NYY",
        "boston red sox": "BOS",
        "chicago cubs": "CHC",
        "los angeles dodgers": "LAD",
        "san francisco giants": "SF",
        "atlanta braves": "ATL",
        "houston astros": "HOU",
        "philadelphia phillies": "PHI",
        "tampa bay rays": "TB",
        "cleveland guardians": "CLE",
        "texas rangers": "TEX",

        # NHL
        "toronto maple leafs": "TOR",
        "boston bruins": "BOS",
        "chicago blackhawks": "CHI",
        "detroit red wings": "DET",
        "new york rangers": "NYR",
        "new jersey devils": "NJD",
        "pittsburgh penguins": "PIT",
        "colorado avalanche": "COL",
        "vegas golden knights": "VGK",
        "tampa bay lightning": "TBL",
    }

    # direct lookup
    if name in replacements:
        return replacements[name]

    # fallback: uppercase abbreviation cleanup
    cleaned = re.sub(r'[^a-zA-Z]', '', name).upper()
    return cleaned[:3]
