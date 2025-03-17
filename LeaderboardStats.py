import requests
import csv
import os
import datetime
import time
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
import pandas as pd
import pyarrow.parquet as pq
import traceback

# API Endpoints
LEADERBOARD_URL = "https://rivalsmeta.com/api/leaderboard/data"

# Primary endpoints (using mrapi.org)
PLAYER_API_URL = "https://mrapi.org/api/player/{}"
PLAYER_UPDATE_URL = "https://mrapi.org/api/player-update/{}"
MATCH_API_URL = "https://mrapi.org/api/match/{}"

# Backup endpoints (using marvelrivalsapi.com)
PLAYER_API_URL_RIVALS = "https://marvelrivalsapi.com/api/v1/player/{}"
PLAYER_UPDATE_URL_RIVALS = "https://marvelrivalsapi.com/api/v1/player/{}/update"
MATCH_API_URL_RIVALS = "https://marvelrivalsapi.com/api/v1/match/{}"

# Filenames
LEADERBOARD_FILE = "data/historical/leaderboard.csv"
PLAYER_ENCOUNTERS_FILE = "data/historical/player_encounters.csv"
MATCHES_FILE = "data/historical/matches.csv"
MATCH_PLAYERS_FILE = "data/historical/match_players/"

# Constants
MAX_PARALLEL_REQUESTS = 10  # Keep this low to avoid hitting API limits
headers = {"x-api-key": os.getenv("API_KEY")}
headers_rivals = {"x-api-key": os.getenv("API_KEY_RIVALS")}
# Rate Limiting
request_count = 0
start_time = time.time()
lock = Lock()
private_profile_count = 0

#thread savety
encountered_lock = Lock() 
match_extra_info = {}

def load_existing_matches():
    """Loads already recorded matches from matches.csv to prevent re-querying them."""
    if not os.path.exists(MATCHES_FILE):
        return set()  # If file doesn’t exist, return an empty set

    existing_matches = set()
    with open(MATCHES_FILE, "r", encoding="utf-8") as f:
        next(f)  # Skip header
        for line in f:
            match_uid = line.strip().split(",")[0]  # Match UID is the first column
            existing_matches.add(match_uid)
    
    print(f"Loaded {len(existing_matches)} existing matches from matches.csv.")
    return existing_matches

def load_existing_players():
    """Loads existing players and their scores to avoid duplicates."""
    if not os.path.exists(PLAYER_ENCOUNTERS_FILE):
        return {}

    players = {}
    with open(PLAYER_ENCOUNTERS_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            players[row["player_uid"]] = {
                "player_name": row["player_name"],
                "highest_score": int(row["highest_score"]) if row["highest_score"].isdigit() else 0,
                "latest_score": int(row["latest_score"]) if row["latest_score"].isdigit() else 0,
                "matches": int(row["matches"]) if row["matches"].isdigit() else 0,
                "wins": int(row["wins"]) if row["wins"].isdigit() else 0,
            }
    print(f"Loaded {len(players)} existing encountered players.")
    return players


# deduplication
queried_matches = load_existing_matches()  # Load past matches from file
queried_players = set()  # Stores already fetched player IDs
encountered_players = load_existing_players()  # Load previously encountered players for teammates list
match_players_data = []
# stat collection

total_scanned_matches = 0
total_scanned_players = 0



def fetch_data(url, retries=10, delay=2, headers_override=None):
    """
    Fetch JSON data safely, handling rate limits and corrupt responses.
    An optional headers_override can be provided.
    """
    global private_profile_count

    for attempt in range(retries):
        try:
            response = requests.get(url, headers=headers_override if headers_override else headers)

            # Detect Rate Limiting (429 Error)
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 5))  # Default 5s if not provided
                print(f"⚠️ Rate limit hit! Sleeping for {retry_after} seconds... (Attempt {attempt+1}/{retries})")
                time.sleep(retry_after)
                continue
            elif response.status_code == 500:
                if "player" in url:  # Only count private profiles for player endpoints
                    print(f"Private profile detected: {url}")
                    private_profile_count += 1
                    return None  # Don't retry on 500 for players
                else:
                    print(f"⚠️ Server error (500) on {url} Retrying... (Attempt {attempt+1}/{retries})")
                    time.sleep(delay)
                    continue
            # For any other API error (like 403)
            if response.status_code >= 400:
                print(f"⚠️ API Error {response.status_code}: Skipping {url}")
                return None

            # Check for Non-JSON Responses
            if "application/json" not in response.headers.get("Content-Type", ""):
                print(f"⚠️ Warning: Non-JSON response from {url}. Skipping...")
                return None

            return response.json()

        except requests.exceptions.RequestException as e:
            print(f"❌ Network error fetching {url}: {e}")
        except ValueError:
            print(f"⚠️ Invalid JSON response from {url}, skipping...")
        time.sleep(delay)

    return None  # If all retries fail

def fetch_with_backup(primary_url, backup_url, retries=10, delay=2):
    """
    Try fetching data using the primary_url. If it fails (i.e. returns None),
    then try the backup_url using the backup header.
    """
    data = fetch_data(primary_url, 3, delay)
    if data is None:
        data = fetch_data(backup_url, retries, delay, headers_override=headers_rivals)
    return data

# Function to append new rows to a CSV file
def append_csv(filename, fieldnames, data, seen_entries=None):
    """Appends data to a CSV file but avoids duplicate entries if seen_entries is provided."""
    if seen_entries is not None:
        entry_key = (data["timestamp"], data["player_uid"])
        if entry_key in seen_entries:
            return  # Skip duplicate
        seen_entries.add(entry_key)

    file_exists = os.path.isfile(filename)
    with open(filename, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow(data)

# Fetch leaderboard
def fetch_leaderboard():
    global total_scanned_matches, total_scanned_players
    print("Fetching leaderboard data...")
    leaderboard = fetch_data(LEADERBOARD_URL)
    if not leaderboard:
        print("Failed to fetch leaderboard.")
        return

    timestamp = datetime.datetime.utcnow().isoformat()

    print(f"Processing {len(leaderboard)} players from leaderboard...")

    players_to_fetch = []

    for idx, player in enumerate(leaderboard["players"]):
        # Add rank based on the position in the leaderboard
        player["rank_in_leaderboard"] = idx + 1  
        player_id = player["uid"]
        if player_id not in queried_players:  # Only fetch if not already queried
            queried_players.add(player_id)
            players_to_fetch.append((player_id, timestamp, player))

    # Fetch all player details in parallel
    total_scanned_players = total_scanned_players + len(players_to_fetch)
    print(f"Fetching {len(players_to_fetch)} players")

    fetch_player_details_parallel(players_to_fetch)

# Fetch match details and save data
def fetch_match_data(match_id):
    """Fetch match details and save match/player data."""
    match_data = fetch_with_backup(MATCH_API_URL.format(match_id),
                                   MATCH_API_URL_RIVALS.format(match_id))
    if not match_data:
        return
    print(f"Processing match {match_id}...")
    # Determine the structure used by the API:
    # If the response contains a "match_details" key, use that (backup format)
    if "match_details" in match_data:
        match_data = match_data["match_details"]
        # Use extra info from match_extra_info if available (e.g., for timestamp, season, map_id, etc.)
        extra = match_extra_info.get(match_id, {})
        csv_data = {
            "match_uid": match_data.get("match_uid", match_id),
            "replay_id": match_data.get("replay_id", ""),
            "gamemode": match_data.get("game_mode", {}).get("game_mode_name", ""),
            "match_timestamp": extra.get("match_timestamp", ""),
            "mvp": match_data.get("mvp_uid", ""),
            "svp": match_data.get("svp_uid", ""),
            "season": extra.get("season", ""),
            "map_id": extra.get("map_id", ""),
            "winning_team_score": extra.get("winning_team_score", ""),
            "losing_team_score": extra.get("losing_team_score", "")
        }
    else:
        # primary format: keys are at the root of the JSON.
        extra = match_extra_info.get(match_id, {})
        csv_data = {
            "match_uid": match_data.get("match_uid", match_id),
            "replay_id": match_data.get("replay_id", ""),
            "gamemode": match_data.get("gamemode", {}).get("name", ""),
            # Backup response does not provide these values; leave them blank.
            "match_timestamp": extra.get("match_timestamp", ""),
            "season": extra.get("season", ""),
            "map_id": extra.get("map_id", ""),
            "mvp": match_data.get("mvp", {}).get("player_uid", ""),
            "svp": match_data.get("svp", {}).get("player_uid", ""),
            "winning_team_score": extra.get("winning_team_score", ""),
            "losing_team_score": extra.get("losing_team_score", "")
        }

    # Save the match JSON data for archival
    match_uid = csv_data.get("match_uid", match_id)
    os.makedirs("data/matches", exist_ok=True)
    with open(os.path.join("data/matches", f"{match_uid}.json"), "w", encoding="utf-8") as f:
        json.dump(match_data, f)

    # Append match details to CSV using safe access for each field.
    append_csv(
        MATCHES_FILE,
        [
            "match_uid",
            "replay_id",
            "gamemode",
            "match_timestamp",
            "season",
            "map_id",
            "mvp",
            "svp",
            "winning_team_score",
            "losing_team_score"
        ],
        csv_data
    )

    # Process match players from the match data.
    for player in match_data.get("match_players", []):
        hero_data = json.dumps(player.get("player_heroes", []), separators=(',', ':'))
        match_players_data.append(
            {
                "match_uid": csv_data.get("match_uid", match_id),
                "player_uid": player.get("player_uid", ""),
                "name": player.get("nick_name", ""),
                "hero_id": player.get("cur_hero_id", ""),
                "is_win": player.get("is_win", ""),
                "kills": player.get("kills", ""),
                "deaths": player.get("deaths", ""),
                "assists": player.get("assists", ""),
                "hero_damage": player.get("total_hero_damage", ""),
                "hero_healed": player.get("total_hero_heal", ""),
                "damage_taken": player.get("total_damage_taken", ""),
                "hero_data": f'"{hero_data}"',
                "match_timestamp": csv_data.get("match_timestamp", "")
            }
        )


# Parallel fetching of player details
def fetch_player_details_parallel(players_to_fetch):
    print(f"Starting parallel fetch for {len(players_to_fetch)} players...")  # Debug line
    with ThreadPoolExecutor(max_workers=MAX_PARALLEL_REQUESTS) as executor:
        future_to_player = {
            executor.submit(fetch_and_process_player, player_id, timestamp, player_data): player_id
            for player_id, timestamp, player_data in players_to_fetch
        }

        for future in as_completed(future_to_player):
            player_id = future_to_player[future]
            print(f"✅ Successfully processed player {player_id}")  # Debug success
            try:
                future.result()
            except Exception as e:
                print(f"Error processing player {player_id}: {e}")
                traceback.print_exc()



# Fetch and process a single player's data
def fetch_and_process_player(player_id, timestamp, leaderboard_entry):
     # Trigger player update
    fetch_with_backup(PLAYER_UPDATE_URL.format(player_id),
                      PLAYER_UPDATE_URL_RIVALS.format(player_id))
    
    player_data = fetch_with_backup(PLAYER_API_URL.format(player_id),
                                    PLAYER_API_URL_RIVALS.format(player_id))
    if not player_data:
        print(f"⚠️ Warning: No data returned for player {player_id}. Skipping...")
        return
    if not isinstance(player_data, dict):
        print(f"🚨 ERROR: Unexpected data type for player {player_id}. Got: {type(player_data)}")
        return
    
    os.makedirs("data/players", exist_ok=True)
    with open(os.path.join("data/players", f"{player_id}.json"), "w", encoding="utf-8") as f:
        json.dump(player_data, f)
    try:    
        # Determine if response is from primary or backup endpoint
        if "stats" in player_data:
            is_private = player_data.get("is_profile_private", True)
            rank_score = "NaN" if is_private else player_data.get("stats", {}).get("rank", {}).get("score", "NaN")
            player_name = player_data.get("player_name", "")
            rank_name = leaderboard_entry.get("rank_name", "")
        else:
            # Backup response structure adjustments
            is_private = player_data.get("isPrivate", True)
            # Try to extract a rank score from one of the season entries (if available)
            rank_game_season = player_data.get("player", {}).get("info", {}).get("rank_game_season", {})
            if rank_game_season and isinstance(rank_game_season, dict) and len(rank_game_season) > 0:
                last_key = sorted(rank_game_season.keys(), key=int)[-1]
                rank_game = rank_game_season[last_key]
                rank_score = rank_game.get("rank_score", "NaN")
            else:
                rank_score = "NaN"
            player_name = player_data.get("player", {}).get("name", "")
            rank_name = player_data.get("player", {}).get("rank", {}).get("rank", "")
    except Exception as e:
        print(f"🚨 ERROR: Exception while processing player {player_id}: {e}")
        print(f"Full player data: {json.dumps(player_data, indent=2)}")
        return  # Skip processing this player to avoid crashing the script        


    # Save leaderboard data, ensuring private profiles are logged
    try:
        append_csv(
            LEADERBOARD_FILE,
            ["timestamp", "rank", "player_name", "rank_name", "score", "matches", "player_id", "rank_score", "is_private"],
            {
                "timestamp": timestamp,
                "rank": leaderboard_entry.get("rank_in_leaderboard",""),
                "player_name": leaderboard_entry.get("name", player_name),
                "rank_name": rank_name,
                "score": leaderboard_entry.get("rank", {}).get("rank_score", ""),
                "matches": leaderboard_entry.get("rank", {}).get("battle_count", 0),
                "player_id": player_id,
                "rank_score": rank_score,  # N/A if private
                "is_private": "Yes" if is_private else "No"
            },
        )
    except Exception as e:
        print(f"Error saving leaderboard data for player {player_id}: {e}")
        print(timestamp)
        print(leaderboard_entry.get("rank_in_leaderboard",""))
        print(leaderboard_entry.get("name", player_name))
        print(rank_name)
        print(leaderboard_entry.get("rank", {}).get("rank_score", ""))
        print(leaderboard_entry.get("rank", {}).get("battle_count", 0))
        print(player_id)
        print(rank_score)
    # Process encountered players (teammates + match opponents)
    process_encountered_players(player_data, timestamp)



# Process teammates and match history
def process_encountered_players(player_data, timestamp):
    global total_scanned_matches, total_scanned_players
    if player_data.get("is_profile_private", player_data.get("isPrivate", True)):
        return

    players_to_fetch = []
    matches_to_fetch = []

    # Process teammates
    if "teammates" in player_data:
        for teammate in player_data["teammates"]:
            pid = teammate.get("player_uid")
            if pid and pid not in queried_players:
                queried_players.add(pid)
                players_to_fetch.append((pid, timestamp))
    elif "team_mates" in player_data:
        for teammate in player_data["team_mates"]:
            pid = teammate.get("player_info", {}).get("player_uid")
            if pid and pid not in queried_players:
                queried_players.add(pid)
                players_to_fetch.append((pid, timestamp))

    # Process match history (only fetch unique matches)
    if "match_history" in player_data:
        for match in player_data["match_history"]:
            match_id = match.get("match_uid")
            print(f"found match_id: {match_id}")
            if match_id and match_id not in queried_matches:
                queried_matches.add(match_id)
                matches_to_fetch.append(match_id)
            
            if match_id not in match_extra_info:
                # Check if we're in the backup structure
                if "score_info" in match:
                    winner_side = match.get("winner_side")
                    score_info = match.get("score_info", {})
                    if not isinstance(score_info, dict): # If a player leaves a game this will be "null"
                        score_info = {}
                    if winner_side and winner_side == 1:
                        winning_score = score_info.get("1", "")
                        losing_score = score_info.get("0", "")
                    elif winner_side and winner_side == 0:
                        winning_score = score_info.get("0", "")
                        losing_score = score_info.get("1", "")
                    else:
                        # fallback: if winner_side missing, choose max/min from score_info
                        try:
                            scores = list(score_info.values())
                            winning_score = max(scores)
                            losing_score = min(scores)
                        except Exception:
                            winning_score = ""
                            losing_score = ""
                    match_timestamp = match.get("match_time_stamp", "")
                    season = match.get("season", "")
                    map_id = match.get("map_id", "")
                else:
                    # Fallback to primary structure
                    is_win = match.get("stats", {}).get("is_win", False)
                    score = match.get("score", {})
                    winning_score = score.get("ally") if is_win else score.get("enemy")
                    losing_score = score.get("enemy") if is_win else score.get("ally")
                    match_timestamp = match.get("match_timestamp", "")
                    season = match.get("season", "")
                    map_id = match.get("match_map", {}).get("id", "")
                match_extra_info[match_id] = {
                    "match_timestamp": match_timestamp,
                    "season": season,
                    "map_id": map_id,
                    "winning_team_score": winning_score,
                    "losing_team_score": losing_score,
                }
    else:
        print(f"Match history not found for player {player_data.get('player_uid', 'UNKNOWN')}")

    # Fetch teammates and matches in parallel
    total_scanned_matches = total_scanned_matches + len(matches_to_fetch)
    total_scanned_players = total_scanned_players + len(players_to_fetch)
    print(f"Fetching {len(players_to_fetch)} encountered players for a total of {total_scanned_players} and {len(matches_to_fetch)} encountered matches for a total of {total_scanned_matches}")
    
    fetch_teammates_parallel(players_to_fetch)
    fetch_matches_parallel(matches_to_fetch)


# Fetch teammates' details in parallel
def fetch_teammates_parallel(players_to_fetch):
    if not players_to_fetch:
        return

    with ThreadPoolExecutor(max_workers=MAX_PARALLEL_REQUESTS) as executor:
        future_to_teammate = {
            executor.submit(fetch_and_process_teammate, player_id): player_id
            for player_id, timestamp in players_to_fetch
        }

        for future in as_completed(future_to_teammate):
            player_id = future_to_teammate[future]
            try:
                future.result()
            except Exception as e:
                print(f"Error processing encountered player {player_id}: {e}")

def save_encountered_players():
    """Saves all encountered players to CSV (no duplicates)."""
    with open(PLAYER_ENCOUNTERS_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["player_uid", "player_name", "highest_score", "latest_score", "matches", "wins"])
        writer.writeheader()
        for player_uid, data in encountered_players.items():
            writer.writerow({
                "player_uid": player_uid,
                "player_name": data["player_name"],
                "highest_score": data["highest_score"],
                "latest_score": data["latest_score"],
                "matches": data["matches"],
                "wins": data["wins"]
            })


# Fetch and process a single teammate's data
def fetch_and_process_teammate(player_id):
    global encountered_players
    player_data = fetch_with_backup(PLAYER_API_URL.format(player_id),
                                    PLAYER_API_URL_RIVALS.format(player_id))
    
    # Return early if no data was fetched
    if not player_data:
        return

    os.makedirs("data/players", exist_ok=True)
    with open(os.path.join("data/players", f"{player_id}.json"), "w", encoding="utf-8") as f:
        json.dump(player_data, f)
    
    # Determine if the profile is private using either key
    is_private = player_data.get("is_profile_private", player_data.get("isPrivate", True))
    if is_private:
        return

    # Process statistics: if "stats" exists use it, otherwise use backup keys
    if "stats" in player_data:
        latest_score = player_data["stats"]["rank"].get("score", 0)
        matches = player_data["stats"].get("total_matches", 0)
        wins = player_data["stats"].get("total_wins", 0)
        player_name = player_data.get("player_name", "")
    else:
        overall_stats = player_data.get("overall_stats", {})
        # In backup responses, total_matches and total_wins are found under "overall_stats"
        latest_score = overall_stats.get("total_matches", 0)  # Fallback value; adjust as needed.
        matches = overall_stats.get("total_matches", 0)
        wins = overall_stats.get("total_wins", 0)
        player_name = player_data.get("player", {}).get("name", "")
    
    print(f"Processing encountered player {player_id} - {'PRIVATE' if is_private else 'PUBLIC'} profile...")
    with encountered_lock:
        if player_id in encountered_players:
            encountered_players[player_id]["latest_score"] = latest_score
            encountered_players[player_id]["matches"] = matches
            encountered_players[player_id]["wins"] = wins
            if latest_score != 0 and latest_score > encountered_players[player_id]["highest_score"]:
                encountered_players[player_id]["highest_score"] = latest_score
        else:
            encountered_players[player_id] = {
                "player_name": player_name,
                "highest_score": latest_score,
                "latest_score": latest_score,
                "matches": matches,
                "wins": wins
            }


# Fetch matches in parallel (avoiding duplicates)
def fetch_matches_parallel(matches_to_fetch):
    if not matches_to_fetch:
        return

    with ThreadPoolExecutor(max_workers=MAX_PARALLEL_REQUESTS) as executor:
        future_to_match = {
            executor.submit(fetch_match_data, match_id): match_id
            for match_id in matches_to_fetch
        }

        for future in as_completed(future_to_match):
            match_id = future_to_match[future]
            try:
                future.result()
            except Exception as e:
                print(f"Error processing match {match_id}: {e}")

def save_to_disk():
    """Writes all collected data to files in one batch."""
    df = pd.DataFrame(match_players_data)
    if "match_timestamp" not in df.columns or df.empty:
        print("No match_timestamp data found in match_players_data!")
        return
    # Convert the match_timestamp column to datetime
    df['match_timestamp'] = pd.to_datetime(df['match_timestamp'], errors='coerce', unit='s')
     # Separate rows with valid and invalid timestamps
    valid_df = df.dropna(subset=['match_timestamp'])
    default_df = df[df['match_timestamp'].isna()]

    # Ensure the directory exists
    os.makedirs(MATCH_PLAYERS_FILE, exist_ok=True)
    if not valid_df.empty:
        # Create week and year columns using ISO calendar
        df['week'] = df['match_timestamp'].dt.isocalendar().week
        df['year'] = df['match_timestamp'].dt.year

        # Group the DataFrame by year and week, then save each group separately
        for (year, week), group in df.groupby(['year', 'week']):
            filename = os.path.join(MATCH_PLAYERS_FILE, f"match_players_week_{week}_{year}.parquet")
            print(f"Saving group for week {week} of {year} to {filename}...")
            if os.path.exists(filename):
                old_data = pd.read_parquet(filename, engine="pyarrow")
                combined_group = pd.concat([old_data, group])
                combined_group.drop_duplicates(subset=["match_uid", "player_uid"], keep="last", inplace=True)
                combined_group.to_parquet(filename, index=False, engine="pyarrow")
            else:
                group.to_parquet(filename, index=False, engine="pyarrow")
    if not default_df.empty:
        default_filename = os.path.join(MATCH_PLAYERS_FILE, "match_players_default.parquet")
        print(f"Saving rows with missing timestamps to {default_filename}...")
        if os.path.exists(default_filename):
            old_data = pd.read_parquet(default_filename, engine="pyarrow")
            combined_default = pd.concat([old_data, default_df])
            combined_default.drop_duplicates(subset=["match_uid", "player_uid"], keep="last", inplace=True)
            combined_default.to_parquet(default_filename, index=False, engine="pyarrow")
        else:
            default_df.to_parquet(default_filename, index=False, engine="pyarrow")


if __name__ == "__main__":
    fetch_leaderboard()
    print(f"Saving {len(encountered_players)} encountered players to CSV...")
    save_encountered_players()
    save_to_disk()
    print("Data collection completed!")
    print(f"Total Players Scanned: {total_scanned_players}")
    print(f"Total Matches Scanned: {total_scanned_matches}")
    print(f"Private Profiles Encountered: {private_profile_count}")
