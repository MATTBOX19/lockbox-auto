#!/usr/bin/env python3
"""
lockbox_learn_stats.py — Merge LockBox predictions with SportsData.io stats

Automated Daily Metrics Learner:
  • Normalizes team names (supports NFL, NCAAF, NBA, MLB, NHL)
  • Merges latest predictions ↔ team stats (with partial-match support)
  • Updates metrics.json and performance.json
"""

import pandas as pd, json, re
from pathlib import Path
from datetime import datetime

OUT_DIR = Path("Output")
DATA_DIR = Path("Data")
STATS_FILE = DATA_DIR / "team_stats_latest.csv"
PRED_FILE = OUT_DIR / "Predictions_latest_Explained.csv"
METRICS_FILE = OUT_DIR / "metrics.json"
PERFORMANCE_FILE = OUT_DIR / "performance.json"

# --- TEAM MAP (All Major Sports) ---
TEAM_MAP = {
    # --- NFL ---
    "ARI": ["ARIZONA CARDINALS", "CARDINALS", "CARDS"],
    "ATL": ["ATLANTA FALCONS", "FALCONS"],
    "BAL": ["BALTIMORE RAVENS", "RAVENS"],
    "BUF": ["BUFFALO BILLS", "BILLS"],
    "CAR": ["CAROLINA PANTHERS", "PANTHERS"],
    "CHI": ["CHICAGO BEARS", "BEARS"],
    "CIN": ["CINCINNATI BENGALS", "BENGALS"],
    "CLE": ["CLEVELAND BROWNS", "BROWNS"],
    "DAL": ["DALLAS COWBOYS", "COWBOYS", "BOYS"],
    "DEN": ["DENVER BRONCOS", "BRONCOS"],
    "DET": ["DETROIT LIONS", "LIONS"],
    "GB": ["GREEN BAY PACKERS", "PACKERS"],
    "HOU": ["HOUSTON TEXANS", "TEXANS"],
    "IND": ["INDIANAPOLIS COLTS", "COLTS"],
    "JAX": ["JACKSONVILLE JAGUARS", "JAGS"],
    "KC": ["KANSAS CITY CHIEFS", "CHIEFS"],
    "LAC": ["LOS ANGELES CHARGERS", "CHARGERS", "L.A. CHARGERS"],
    "LAR": ["LOS ANGELES RAMS", "RAMS", "L.A. RAMS"],
    "LV": ["LAS VEGAS RAIDERS", "RAIDERS"],
    "MIA": ["MIAMI DOLPHINS", "DOLPHINS", "FINS"],
    "MIN": ["MINNESOTA VIKINGS", "VIKINGS", "VIKES"],
    "NE": ["NEW ENGLAND PATRIOTS", "PATRIOTS", "PATS"],
    "NO": ["NEW ORLEANS SAINTS", "SAINTS"],
    "NYG": ["NEW YORK GIANTS", "GIANTS", "NYG"],
    "NYJ": ["NEW YORK JETS", "JETS", "NYJ"],
    "PHI": ["PHILADELPHIA EAGLES", "EAGLES"],
    "PIT": ["PITTSBURGH STEELERS", "STEELERS"],
    "SF": ["SAN FRANCISCO 49ERS", "49ERS", "NINERS"],
    "SEA": ["SEATTLE SEAHAWKS", "SEAHAWKS", "HAWKS"],
    "TB": ["TAMPA BAY BUCCANEERS", "BUCCANEERS", "BUCS"],
    "TEN": ["TENNESSEE TITANS", "TITANS"],
    "WAS": ["WASHINGTON COMMANDERS", "COMMANDERS", "WASHINGTON"],

       # --- NBA ---
    "ATL_NBA": ["ATLANTA HAWKS", "HAWKS"],
    "BOS_NBA": ["BOSTON CELTICS", "CELTICS", "CS"],
    "BKN": ["BROOKLYN NETS", "NETS"],
    "CHA": ["CHARLOTTE HORNETS", "HORNETS"],
    "CHI_NBA": ["CHICAGO BULLS", "BULLS"],
    "CLE_NBA": ["CLEVELAND CAVALIERS", "CAVS"],
    "DAL_NBA": ["DALLAS MAVERICKS", "MAVERICKS", "MAVS"],
    "DEN_NBA": ["DENVER NUGGETS", "NUGGETS", "NUGS"],
    "DET_NBA": ["DETROIT PISTONS", "PISTONS"],
    "GSW": ["GOLDEN STATE WARRIORS", "WARRIORS", "DUBS"],
    "HOU_NBA": ["HOUSTON ROCKETS", "ROCKETS"],
    "IND_NBA": ["INDIANA PACERS", "PACERS"],
    "LAC_NBA": ["LOS ANGELES CLIPPERS", "CLIPPERS", "CLIPS"],
    "LAL": ["LOS ANGELES LAKERS", "LAKERS"],
    "MEM": ["MEMPHIS GRIZZLIES", "GRIZZLIES", "GRIZZ"],
    "MIA_NBA": ["MIAMI HEAT", "HEAT"],
    "MIL": ["MILWAUKEE BUCKS", "BUCKS"],
    "MIN_NBA": ["MINNESOTA TIMBERWOLVES", "TIMBERWOLVES", "WOLVES"],
    "NOP": ["NEW ORLEANS PELICANS", "PELICANS", "PELS"],
    "NYK": ["NEW YORK KNICKS", "KNICKS"],
    "OKC": ["OKLAHOMA CITY THUNDER", "THUNDER"],
    "ORL": ["ORLANDO MAGIC", "MAGIC"],
    "PHI_NBA": ["PHILADELPHIA 76ERS", "SIXERS", "76ERS"],
    "PHX": ["PHOENIX SUNS", "SUNS"],
    "POR": ["PORTLAND TRAIL BLAZERS", "BLAZERS"],
    "SAC": ["SACRAMENTO KINGS", "KINGS"],
    "SAS": ["SAN ANTONIO SPURS", "SPURS"],
    "TOR": ["TORONTO RAPTORS", "RAPTORS", "RAPS"],
    "UTA": ["UTAH JAZZ", "JAZZ"],
    "WAS_NBA": ["WASHINGTON WIZARDS", "WIZARDS"],

       # --- MLB ---
    "ARI_MLB": ["ARIZONA DIAMONDBACKS", "DIAMONDBACKS", "D-BACKS"],
    "ATL_MLB": ["ATLANTA BRAVES", "BRAVES"],
    "BAL_MLB": ["BALTIMORE ORIOLES", "ORIOLES", "OS"],
    "BOS_MLB": ["BOSTON RED SOX", "RED SOX", "SOX"],
    "CHC": ["CHICAGO CUBS", "CUBS"],
    "CHW": ["CHICAGO WHITE SOX", "WHITE SOX", "SOX"],
    "CIN_MLB": ["CINCINNATI REDS", "REDS"],
    "CLE_MLB": ["CLEVELAND GUARDIANS", "GUARDIANS"],
    "COL": ["COLORADO ROCKIES", "ROCKIES"],
    "DET_MLB": ["DETROIT TIGERS", "TIGERS"],
    "HOU_MLB": ["HOUSTON ASTROS", "ASTROS", "STROS"],
    "KC": ["KANSAS CITY ROYALS", "ROYALS"],
    "LAA": ["LOS ANGELES ANGELS", "ANGELS", "HALOS"],
    "LAD": ["LOS ANGELES DODGERS", "DODGERS"],
    "MIA_MLB": ["MIAMI MARLINS", "MARLINS"],
    "MIL_MLB": ["MILWAUKEE BREWERS", "BREWERS", "BREW CREW"],
    "MIN_MLB": ["MINNESOTA TWINS", "TWINS"],
    "NYM": ["NEW YORK METS", "METS"],
    "NYY": ["NEW YORK YANKEES", "YANKEES", "YANKS"],
    "OAK": ["OAKLAND ATHLETICS", "ATHLETICS", "AS"],
    "PHI_MLB": ["PHILADELPHIA PHILLIES", "PHILLIES", "PHILS"],
    "PIT_MLB": ["PITTSBURGH PIRATES", "PIRATES", "BUCS"],
    "SD": ["SAN DIEGO PADRES", "PADRES"],
    "SF_MLB": ["SAN FRANCISCO GIANTS", "GIANTS"],
    "SEA_MLB": ["SEATTLE MARINERS", "MARINERS", "MS"],
    "STL": ["ST LOUIS CARDINALS", "CARDINALS", "CARDS"],
    "TB_MLB": ["TAMPA BAY RAYS", "RAYS"],
    "TEX": ["TEXAS RANGERS", "RANGERS"],
    "TOR_MLB": ["TORONTO BLUE JAYS", "BLUE JAYS", "JAYS"],
    "WSH_MLB": ["WASHINGTON NATIONALS", "NATIONALS", "NATS"],

       # --- NHL ---
    "ANA": ["ANAHEIM DUCKS", "DUCKS"],
    "ARI_NHL": ["ARIZONA COYOTES", "COYOTES", "YOTES"],
    "BOS_NHL": ["BOSTON BRUINS", "BRUINS"],
    "BUF_NHL": ["BUFFALO SABRES", "SABRES"],
    "CAR_NHL": ["CAROLINA HURRICANES", "HURRICANES", "CANES"],
    "CBJ": ["COLUMBUS BLUE JACKETS", "BLUE JACKETS", "JACKETS"],
    "CGY": ["CALGARY FLAMES", "FLAMES"],
    "CHI_NHL": ["CHICAGO BLACKHAWKS", "BLACKHAWKS", "HAWKS"],
    "COL_NHL": ["COLORADO AVALANCHE", "AVALANCHE", "AVS"],
    "DAL_NHL": ["DALLAS STARS", "STARS"],
    "DET_NHL": ["DETROIT RED WINGS", "RED WINGS", "WINGS"],
    "EDM_NHL": ["EDMONTON OILERS", "OILERS"],
    "FLA": ["FLORIDA PANTHERS", "PANTHERS"],
    "LAK": ["LOS ANGELES KINGS", "KINGS"],
    "MIN_NHL": ["MINNESOTA WILD", "WILD"],
    "MTL": ["MONTREAL CANADIENS", "CANADIENS", "HABS"],
    "NSH": ["NASHVILLE PREDATORS", "PREDATORS", "PREDS"],
    "NJD": ["NEW JERSEY DEVILS", "DEVILS"],
    "NYI": ["NEW YORK ISLANDERS", "ISLANDERS", "ISLES"],
    "NYR_NHL": ["NEW YORK RANGERS", "RANGERS"],
    "OTT": ["OTTAWA SENATORS", "SENATORS", "SENS"],
    "PHI_NHL": ["PHILADELPHIA FLYERS", "FLYERS"],
    "PIT_NHL": ["PITTSBURGH PENGUINS", "PENGUINS", "PENS"],
    "SEA_NHL": ["SEATTLE KRAKEN", "KRAKEN"],
    "SJS": ["SAN JOSE SHARKS", "SHARKS"],
    "STL_NHL": ["ST LOUIS BLUES", "BLUES"],
    "TBL": ["TAMPA BAY LIGHTNING", "LIGHTNING", "BOLTS"],
    "TOR_NHL": ["TORONTO MAPLE LEAFS", "MAPLE LEAFS", "LEAFS"],
    "VAN": ["VANCOUVER CANUCKS", "CANUCKS"],
    "VGK": ["VEGAS GOLDEN KNIGHTS", "GOLDEN KNIGHTS", "VGK"],
    "WPG": ["WINNIPEG JETS", "JETS"],
    "WSH_NHL": ["WASHINGTON CAPITALS", "CAPITALS", "CAPS"],

       # --- NCAAF ---
    "ALA": ["ALABAMA CRIMSON TIDE", "ALABAMA", "BAMA"],
    "UGA": ["GEORGIA BULLDOGS", "GEORGIA", "DAWGS"],
    "LSU": ["LSU TIGERS", "LOUISIANA STATE"],
    "TEX": ["TEXAS LONGHORNS", "TEXAS", "HORNS"],
    "OU": ["OKLAHOMA SOONERS", "OKLAHOMA"],
    "OSU": ["OHIO STATE BUCKEYES", "OHIO STATE", "BUCKEYES"],
    "MICH": ["MICHIGAN WOLVERINES", "MICHIGAN"],
    "USC": ["SOUTHERN CALIFORNIA TROJANS", "USC TROJANS", "TROJANS"],
    "PSU": ["PENN STATE NITTANY LIONS", "PENN STATE", "NITTANY LIONS"],
    "ND": ["NOTRE DAME FIGHTING IRISH", "NOTRE DAME", "IRISH"],
    "ORE": ["OREGON DUCKS", "OREGON", "DUCKS"],
    "WASH": ["WASHINGTON HUSKIES", "WASHINGTON"],
    "TENN": ["TENNESSEE VOLUNTEERS", "TENNESSEE", "VOLS"],
    "FSU": ["FLORIDA STATE SEMINOLES", "FLORIDA STATE", "NOLES"],
    "CLEM": ["CLEMSON TIGERS", "CLEMSON"],
    "AUB": ["AUBURN TIGERS", "AUBURN"],
    "TAMU": ["TEXAS A&M AGGIES", "TEXAS A&M", "AGGIES"],
    "FL": ["FLORIDA GATORS", "FLORIDA", "GATORS"],
    "UNC": ["NORTH CAROLINA TAR HEELS", "NORTH CAROLINA", "TAR HEELS"],
    "NCST": ["NC STATE WOLFPACK", "NORTH CAROLINA STATE", "WOLFPACK"],
    "MIAMI": ["MIAMI HURRICANES", "MIAMI (FL)", "CANES"],
    "VT": ["VIRGINIA TECH HOKIES", "VIRGINIA TECH"],
    "WISC": ["WISCONSIN BADGERS", "WISCONSIN"],
    "IOWA": ["IOWA HAWKEYES", "IOWA"],
    "MINN": ["MINNESOTA GOLDEN GOPHERS", "MINNESOTA", "GOPHERS"],
    "NEB": ["NEBRASKA CORNHUSKERS", "NEBRASKA", "HUSKERS"],
    "MSU": ["MICHIGAN STATE SPARTANS", "MICHIGAN STATE", "SPARTANS"],
    "IU": ["INDIANA HOOSIERS", "INDIANA"],
    "UK": ["KENTUCKY WILDCATS", "KENTUCKY"],
    "BAY": ["BAYLOR BEARS", "BAYLOR"],
    "TTU": ["TEXAS TECH RED RAIDERS", "TEXAS TECH", "RED RAIDERS"],
    "KSU": ["KANSAS STATE WILDCATS", "KANSAS STATE"],
    "KU": ["KANSAS JAYHAWKS", "KANSAS"],
    "OLE": ["OLE MISS REBELS", "MISSISSIPPI REBELS", "REBELS"],
    "MISS": ["MISSISSIPPI STATE BULLDOGS", "MISSISSIPPI STATE"],
    "ARK": ["ARKANSAS RAZORBACKS", "ARKANSAS", "HOGS"],
    "MIZZ": ["MISSOURI TIGERS", "MISSOURI"],
    "UVA": ["VIRGINIA CAVALIERS", "VIRGINIA", "HOOS"],
    "CAL": ["CALIFORNIA GOLDEN BEARS", "CALIFORNIA", "GOLDEN BEARS"],
    "STAN": ["STANFORD CARDINAL", "STANFORD"],
    "UCLA": ["UCLA BRUINS", "BRUINS"],
    "AZ": ["ARIZONA WILDCATS", "ARIZONA"],
    "ASU": ["ARIZONA STATE SUN DEVILS", "ARIZONA STATE", "SUN DEVILS"],
    "COLO": ["COLORADO BUFFALOES", "COLORADO", "BUFFS"],
    "UTAH": ["UTAH UTES", "UTAH"],
    "OKST": ["OKLAHOMA STATE COWBOYS", "OKLAHOMA STATE", "COWBOYS"],
    "TCU": ["TCU HORNED FROGS", "TEXAS CHRISTIAN", "HORNED FROGS"],
    "SMU": ["SMU MUSTANGS", "SOUTHERN METHODIST", "MUSTANGS"],
    "HOU": ["HOUSTON COUGARS", "HOUSTON"],
    "WVU": ["WEST VIRGINIA MOUNTAINEERS", "WEST VIRGINIA"],
    "PITT": ["PITTSBURGH PANTHERS", "PITTSBURGH"],
    "LOU": ["LOUISVILLE CARDINALS", "LOUISVILLE"],
    "GT": ["GEORGIA TECH YELLOW JACKETS", "GEORGIA TECH"],
    "SYR": ["SYRACUSE ORANGE", "SYRACUSE"],
    "BC": ["BOSTON COLLEGE EAGLES", "BOSTON COLLEGE"],
    "NAVY": ["NAVY MIDSHIPMEN", "NAVY"],
    "ARMY": ["ARMY BLACK KNIGHTS", "ARMY"],
    "AIRF": ["AIR FORCE FALCONS", "AIR FORCE"],
    "BOISE": ["BOISE STATE BRONCOS", "BOISE STATE"],
    "SDSU": ["SAN DIEGO STATE AZTECS", "SAN DIEGO STATE"],
    "FRES": ["FRESNO STATE BULLDOGS", "FRESNO STATE"],
    "SJSU": ["SAN JOSE STATE SPARTANS", "SAN JOSE STATE"],
    "UNLV": ["UNLV REBELS", "NEVADA LAS VEGAS", "REBELS"],
    "NEV": ["NEVADA WOLF PACK", "NEVADA"],
    "HAW": ["HAWAII RAINBOW WARRIORS", "HAWAII"],
    "CSU": ["COLORADO STATE RAMS", "COLORADO STATE"],
    "UCF": ["UCF KNIGHTS", "CENTRAL FLORIDA", "KNIGHTS"],
    "USF": ["USF BULLS", "SOUTH FLORIDA", "BULLS"],
    "MEM": ["MEMPHIS TIGERS", "MEMPHIS"],
    "TUL": ["TULANE GREEN WAVE", "TULANE"],
    "ECU": ["EAST CAROLINA PIRATES", "EAST CAROLINA"],
    "UCONN": ["CONNECTICUT HUSKIES", "UCONN", "CONNECTICUT"],
    "RUT": ["RUTGERS SCARLET KNIGHTS", "RUTGERS"],
      "NW": ["NORTHWESTERN WILDCATS", "NORTHWESTERN"],
    "PUR": ["PURDUE BOILERMAKERS", "PURDUE"],
    "ILL": ["ILLINOIS FIGHTING ILLINI", "ILLINOIS", "ILLINI"],
    "MD": ["MARYLAND TERRAPINS", "MARYLAND", "TERPS"],
    "DUKE": ["DUKE BLUE DEVILS", "DUKE"],
    "TROY": ["TROY TROJANS", "TROY"],
    "APP": ["APPALACHIAN STATE MOUNTAINEERS", "APPALACHIAN STATE", "APP STATE"],
    "GASO": ["GEORGIA SOUTHERN EAGLES", "GEORGIA SOUTHERN"],
    "GAST": ["GEORGIA STATE PANTHERS", "GEORGIA STATE"],
    "COAST": ["COASTAL CAROLINA CHANTICLEERS", "COASTAL CAROLINA"],
    "JMU": ["JAMES MADISON DUKES", "JAMES MADISON"],
    "ODU": ["OLD DOMINION MONARCHS", "OLD DOMINION"],
    "MARSH": ["MARSHALL THUNDERING HERD", "MARSHALL"],
    "MTSU": ["MIDDLE TENNESSEE BLUE RAIDERS", "MIDDLE TENNESSEE"],
    "WKU": ["WESTERN KENTUCKY HILLTOPPERS", "WESTERN KENTUCKY"],
    "UAB": ["UAB BLAZERS", "ALABAMA BIRMINGHAM"],
    "UTSA": ["UTSA ROADRUNNERS", "TEXAS SAN ANTONIO"],
    "UTEP": ["UTEP MINERS", "TEXAS EL PASO"],
    "UNT": ["NORTH TEXAS MEAN GREEN", "NORTH TEXAS"],
    "FAU": ["FLORIDA ATLANTIC OWLS", "FLORIDA ATLANTIC"],
    "FIU": ["FLORIDA INTERNATIONAL PANTHERS", "FLORIDA INTERNATIONAL"],
    "CHAR": ["CHARLOTTE 49ERS", "CHARLOTTE"],
    "USM": ["SOUTHERN MISS GOLDEN EAGLES", "SOUTHERN MISS", "SOUTHERN MISSISSIPPI"],
    "RICE": ["RICE OWLS", "RICE"],
    "LT": ["LOUISIANA TECH BULLDOGS", "LOUISIANA TECH"],
    "ULL": ["LOUISIANA RAGIN CAJUNS", "LOUISIANA LAFAYETTE", "LOUISIANA"],
    "ULM": ["LOUISIANA MONROE WARHAWKS", "LOUISIANA MONROE"],
    "ARKST": ["ARKANSAS STATE RED WOLVES", "ARKANSAS STATE"],
    "TXST": ["TEXAS STATE BOBCATS", "TEXAS STATE"],
    "NMSU": ["NEW MEXICO STATE AGGIES", "NEW MEXICO STATE"],
    "NM": ["NEW MEXICO LOBOS", "NEW MEXICO"],
    "UTAHST": ["UTAH STATE AGGIES", "UTAH STATE"],
    "BYU": ["BYU COUGARS", "BRIGHAM YOUNG"],
    "IDAHO": ["IDAHO VANDALS", "IDAHO"],
    "UWM": ["WYOMING COWBOYS", "WYOMING"],
    "UNM": ["NEW MEXICO LOBOS", "NEW MEXICO"],
    "SJST": ["SAN JOSE STATE SPARTANS", "SAN JOSE STATE"],
    "CSUN": ["COLORADO STATE RAMS", "COLORADO STATE"],
    "TOL": ["TOLEDO ROCKETS", "TOLEDO"],
    "BGSU": ["BOWLING GREEN FALCONS", "BOWLING GREEN"],
    "CMU": ["CENTRAL MICHIGAN CHIPPEWAS", "CENTRAL MICHIGAN"],
    "WMU": ["WESTERN MICHIGAN BRONCOS", "WESTERN MICHIGAN"],
    "EMU": ["EASTERN MICHIGAN EAGLES", "EASTERN MICHIGAN"],
    "NIU": ["NORTHERN ILLINOIS HUSKIES", "NORTHERN ILLINOIS"],
    "AKRON": ["AKRON ZIPS", "AKRON"],
    "KENT": ["KENT STATE GOLDEN FLASHES", "KENT STATE"],
    "OHIO": ["OHIO BOBCATS", "OHIO"],
    "BALL": ["BALL STATE CARDINALS", "BALL STATE"],
    "BUFF": ["BUFFALO BULLS", "BUFFALO"],
    "MIAMIOH": ["MIAMI (OH) REDHAWKS", "MIAMI OHIO", "REDHAWKS"],
    "UCFB": ["CENTRAL FLORIDA KNIGHTS", "UCF", "KNIGHTS"],
    "GSU": ["GEORGIA STATE PANTHERS", "GEORGIA STATE"],
    "TEXSAN": ["TEXAS SAN ANTONIO ROADRUNNERS", "UTSA"],
    "TXELP": ["TEXAS EL PASO MINERS", "UTEP"],
    "LIB": ["LIBERTY FLAMES", "LIBERTY"],
    "SAMH": ["SAM HOUSTON BEARKATS", "SAM HOUSTON"],
    "JAXST": ["JACKSONVILLE STATE GAMECOCKS", "JACKSONVILLE STATE"],
    "KSUF": ["KENNESAW STATE OWLS", "KENNESAW STATE"],
}

# --- Utility helpers ---
def normalize_team(t):
    """Clean and normalize team string to match TEAM_MAP aliases."""
    if not isinstance(t, str):
        return ""
    t = t.strip().upper()
    t = re.sub(r"\(.*?\)", "", t)
    t = re.sub(r"[^A-Z0-9]", "", t)
    t = re.sub(r"(NFL|NBA|MLB|NHL|NCAAF)$", "", t)
    for abbr, aliases in TEAM_MAP.items():
        clean_aliases = [re.sub(r"[^A-Z0-9]", "", a.upper()) for a in aliases]
        if t == abbr or t in clean_aliases:
            return abbr
    return t


def safe_mean(series):
    try:
        return round(series.dropna().astype(float).mean(), 3)
    except Exception:
        return 0.0


def main():
    if not PRED_FILE.exists() or not STATS_FILE.exists():
        print("❌ Missing required files.")
        return

    preds = pd.read_csv(PRED_FILE)
    stats = pd.read_csv(STATS_FILE)

    preds.columns = [c.lower().strip() for c in preds.columns]
    stats.columns = [c.lower().strip() for c in stats.columns]

    # --- Normalize possible sport/league naming ---
    if "sport" in stats.columns:
        stats = stats.rename(columns={"sport": "league"})

    team_col = next((c for c in ["bestpick", "team1", "home", "team"] if c in preds.columns), None)
    if not team_col:
        print(f"⚠️ No usable team column found. Columns: {list(preds.columns)}")
        return

    print(f"✅ Using team column(s): ['{team_col}']")

    # --- improved normalization & merge logic ---
    def normalize_name(x: str) -> str:
        if not isinstance(x, str):
            return ""
        x = x.upper().strip()
        x = re.sub(r"\(.*?\)", "", x)  # remove (ATS), (ML), etc.
        x = re.sub(r"[^A-Z0-9 ]+", "", x)
        x = re.sub(r"\s+", " ", x)
        return x.strip()

    # build a quick alias → abbr lookup
    ALIAS_TO_ABBR = {}
    for abbr, aliases in TEAM_MAP.items():
        ALIAS_TO_ABBR[abbr] = abbr
        for alias in aliases:
            ALIAS_TO_ABBR[normalize_name(alias)] = abbr

    def to_key(s: str) -> str:
        n = normalize_name(s)
        return ALIAS_TO_ABBR.get(n, n)  # mapped abbr if known, else cleaned text

    # normalize predictions team names
    preds["team_key"] = preds[team_col].astype(str).apply(to_key)

    # --- handle game-level stats with Home/Away ---
    if "team" in stats.columns:
        stats["team_key"] = stats["team"].astype(str).apply(to_key)
    elif "home" in stats.columns and "away" in stats.columns:
        home_df = stats[["home", "league", "homescore", "homeyards", "hometurnovers", "homepossession"]].copy()
        home_df.columns = ["team", "league", "score", "yards", "turnovers", "possession"]
        away_df = stats[["away", "league", "awayscore", "awayyards", "awayturnovers", "awaypossession"]].copy()
        away_df.columns = ["team", "league", "score", "yards", "turnovers", "possession"]
        stats = pd.concat([home_df, away_df], ignore_index=True)
        stats["team_key"] = stats["team"].astype(str).apply(to_key)
    else:
        stats["team_key"] = ""

    # --- improved merge logic (no external deps) ---
    merged_rows, unmatched = [], set()

    # build aggregated stats lookup by team_key (average numeric fields if multiple rows)
    numeric_cols = ["score", "yards", "turnovers", "possession"]
    stats_by_key = {}
    for _, srow in stats.iterrows():
        k = str(srow.get("team_key", "")).strip()
        if not k:
            continue
        if k not in stats_by_key:
            stats_by_key[k] = {"team_raw": str(srow.get("team", "") or k), "league": srow.get("league", None)}
            for nc in numeric_cols:
                stats_by_key[k][nc] = []
        for nc in numeric_cols:
            val = srow.get(nc)
            try:
                if pd.isna(val):
                    continue
            except Exception:
                pass
            if isinstance(val, (int, float)):
                stats_by_key[k][nc].append(float(val))
            else:
                try:
                    stats_by_key[k][nc].append(float(str(val)))
                except Exception:
                    continue

    # finalize aggregated values (mean) and keep a representative row dict
    for k, info in list(stats_by_key.items()):
        agg = {}
        for nc in numeric_cols:
            vals = info.get(nc, [])
            agg[nc] = (round(sum(vals) / len(vals), 3) if vals else None)
        agg["team"] = info.get("team_raw", k)
        agg["league"] = info.get("league")
        stats_by_key[k] = agg

    stats_team_keys = list(stats_by_key.keys())
    stats_team_keys_set = set(stats_team_keys)

    # league suffix helpers
    LEAGUE_SUFFIXES = ["_NFL", "_NBA", "_MLB", "_NHL", "_NCAAF"]

    def try_suffix_variants(key):
        """Try remove or add league suffixes to find a candidate in stats_by_key."""
        if not isinstance(key, str) or not key:
            return None
        # remove suffix if present
        for suf in LEAGUE_SUFFIXES:
            if key.endswith(suf):
                base = key[:-len(suf)]
                if base in stats_team_keys_set:
                    return base
        # add suffixes
        for suf in LEAGUE_SUFFIXES:
            cand = key + suf
            if cand in stats_team_keys_set:
                return cand
        return None

    def token_overlap_best(pred_text):
        """Return best matching stats key by token overlap (Jaccard-like)."""
        if not isinstance(pred_text, str):
            return None
        pnorm = normalize_name(pred_text)
        ptoks = set(pnorm.split())
        if not ptoks:
            return None
        best, best_score = None, 0.0
        for k, info in stats_by_key.items():
            raw = info.get("team", k)
            rnorm = normalize_name(raw)
            rtoks = set(rnorm.split())
            if not rtoks:
                continue
            inter = ptoks & rtoks
            union = ptoks | rtoks
            score = (len(inter) / len(union)) if union else 0.0
            # prefer exact token subset matches (boost)
            if ptoks <= rtoks:
                score += 0.15
            if score > best_score:
                best_score = score
                best = k
        # threshold to avoid wild matches
        return best if best_score >= 0.35 else None

    def startswith_match(pred_text):
        """Simple heuristic: match if pred tokens start the stats team name."""
        if not isinstance(pred_text, str):
            return None
        pnorm = normalize_name(pred_text)
        for k, info in stats_by_key.items():
            rnorm = normalize_name(info.get("team", k))
            if rnorm.startswith(pnorm) or pnorm.startswith(rnorm):
                return k
        return None

    # Main merge loop with fallbacks
    for _, prow in preds.iterrows():
        tkey = str(prow.get("team_key", "")).strip()
        raw_pred = str(prow.get(team_col, "") or tkey)

        if not tkey and not raw_pred:
            continue

        matched_key = None

        # 1) exact on team_key
        if tkey in stats_team_keys_set:
            matched_key = tkey

        # 2) normalized map (normalize_team may map variants to abbrs)
        if not matched_key:
            alt = normalize_team(tkey)
            if alt and alt in stats_team_keys_set:
                matched_key = alt

        # 3) suffix add/remove
        if not matched_key:
            alt = try_suffix_variants(tkey)
            if alt:
                matched_key = alt

        # 4) token overlap on the original prediction string
        if not matched_key:
            cand = token_overlap_best(raw_pred)
            if cand:
                matched_key = cand

        # 5) token overlap on the team_key text (in case team_key is cleaned phrase)
        if not matched_key:
            cand = token_overlap_best(tkey)
            if cand:
                matched_key = cand

        # 6) startswith heuristic
        if not matched_key:
            cand = startswith_match(raw_pred)
            if cand:
                matched_key = cand

        if not matched_key:
            unmatched.add(tkey or raw_pred)
            continue

        # compose merged row
        merged = {**prow.to_dict()}

        sinfo = stats_by_key.get(matched_key, {})
        # attach aggregated numeric stats if available
        for nc in numeric_cols:
            val = sinfo.get(nc)
            if val is not None:
                merged[nc] = float(val)
        # attach matched metadata for QA
        merged["_matched_team_key"] = matched_key
        merged["_matched_team_raw"] = sinfo.get("team", "")

        merged_rows.append(merged)

    # Diagnostics for unmatched teams (short sample)
    if unmatched:
        um_sorted = sorted(list(unmatched))
        sample = um_sorted[:30]
        print(f"⚠️ Unmatched teams ({len(unmatched)}). Sample: {sample}")

    if not merged_rows:
        print("⚠️ No matching games found to merge.")
        return

    merged = pd.DataFrame(merged_rows)
    print(f"✅ Merged {len(merged)} predictions with team stat records")

    summary = {
        "timestamp": datetime.utcnow().isoformat(),
        "games": len(merged),
        "avg_edge": safe_mean(merged.get("edge", pd.Series(dtype=float))),
        "avg_confidence": safe_mean(merged.get("confidence", pd.Series(dtype=float))),
        "avg_epa_off": safe_mean(merged.get("epa_off", pd.Series(dtype=float))),
        "avg_epa_def": safe_mean(merged.get("epa_def", pd.Series(dtype=float))),
        "avg_success_off": safe_mean(merged.get("success_off", pd.Series(dtype=float))),
        "avg_success_def": safe_mean(merged.get("success_def", pd.Series(dtype=float))),
        "avg_pace": safe_mean(merged.get("pace", pd.Series(dtype=float))),
    }

    with open(METRICS_FILE, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"🧠 Updated metrics.json with {summary['games']} merged games")

    perf = {
        "updated": summary["timestamp"],
        "overall": {"edge": summary["avg_edge"], "confidence": summary["avg_confidence"]},
    }
    with open(PERFORMANCE_FILE, "w") as f:
        json.dump(perf, f, indent=2)
    print("📊 performance.json written")

    if unmatched:
        print(f"⚠️ Unmatched teams ({len(unmatched)}): {sorted(list(unmatched))[:20]}...")


if __name__ == "__main__":
    main()
