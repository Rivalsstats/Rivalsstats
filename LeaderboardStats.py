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

# API Endpoints
LEADERBOARD_URL = "https://mrapi.org/api/leaderboard"
PLAYER_API_URL = "https://mrapi.org/api/player/{}"
MATCH_API_URL = "https://mrapi.org/api/match/{}"

# Filenames
LEADERBOARD_FILE = "data/historical/leaderboard.csv"
PLAYER_ENCOUNTERS_FILE = "data/historical/player_encounters.csv"
MATCHES_FILE = "data/historical/matches.csv"
MATCH_PLAYERS_FILE = "data/historical/match_players.parquet"

# Constants
MAX_PARALLEL_REQUESTS = 10  # Keep this low to avoid hitting API limits
API_LIMIT = 480  # Max API calls per minute is 500 but we do 480 to be safe
API_DELAY = 60 / API_LIMIT  # Time per request to stay within limits

# Rate Limiting
request_count = 0
start_time = time.time()
lock = Lock()
private_profile_count = 0

#thread savety
encountered_lock = Lock() 

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



def rate_limited_fetch(url):
    """Fetch API data while ensuring global rate limits are not exceeded."""
    global request_count, start_time

    with lock:
        elapsed_time = time.time() - start_time

        # Reset counter if a minute has passed
        if elapsed_time >= 60:
            request_count = 0
            start_time = time.time()

        # If request limit is reached, wait until reset
        if request_count >= API_LIMIT:
            wait_time = 60 - elapsed_time
            print(f"Rate limit reached! Sleeping for {wait_time:.2f} seconds...")
            time.sleep(wait_time)
            request_count = 0
            start_time = time.time()

        request_count += 1

    return fetch_data(url)


def fetch_data(url, retries=3, delay=2):
    """Fetch JSON data safely, handling rate limits and corrupt responses."""
    global private_profile_count

    for attempt in range(retries):
        try:
            response = requests.get(url)

            # Detect Rate Limiting (429 Error)
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 5))  # Default 5s if not provided
                print(f"⚠️ Rate limit hit! Sleeping for {retry_after} seconds...")
                time.sleep(retry_after)
                continue  # Retry after sleep
            elif response.status_code == 500:
                print(f"Private profile detected: {url}")
                private_profile_count += 1
                return None  # Don't retry on 500
            # Detect API Errors (500, 403, etc.)
            if response.status_code >= 400:
                print(f"⚠️ API Error {response.status_code}: Skipping {url}")
                return None

            # Detect Non-JSON Responses
            content_type = response.headers.get("Content-Type", "")
            if "application/json" not in content_type:
                print(f"⚠️ Warning: Non-JSON response from {url}. Skipping...")
                return None

            # Try parsing JSON safely
            return response.json()

        except requests.exceptions.RequestException as e:
            print(f"❌ Network error fetching {url}: {e}")
        except ValueError:
            print(f"⚠️ Invalid JSON response from {url}, skipping...")
        time.sleep(delay)

    return None  # If all retries fail



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
    leaderboard = rate_limited_fetch(LEADERBOARD_URL)
    if not leaderboard:
        print("Failed to fetch leaderboard.")
        return

    timestamp = datetime.datetime.utcnow().isoformat()

    print(f"Processing {len(leaderboard)} players from leaderboard...")

    players_to_fetch = []

    for player in leaderboard:
        player_id = player["player_id"]
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
    global match_players_data
    match_data = rate_limited_fetch(MATCH_API_URL.format(match_id))
    if not match_data:
        return

    print(f"Processing match {match_id}...")

    # Save match details
    append_csv(
        MATCHES_FILE,
        ["match_uid", "replay_id", "gamemode"],
        {
            "match_uid": match_data["match_uid"],
            "replay_id": match_data["replay_id"],
            "gamemode": match_data["gamemode"]["name"],
        },
    )

    # Save match players
    for player in match_data["players"]:
        hero_data = [
            {
                "hero_id": hero["hero_id"],
                "playtime": hero["playtime"]["raw"],
                "kills": hero["kills"],
                "deaths": hero["deaths"],
                "assists": hero["assists"],
                "hit_rate": hero["hit_rate"],
            }
            for hero in player.get("heroes", [])
        ]
        hero_data_str = json.dumps(hero_data, separators=(',', ':'))
        match_players_data.append(
            {
                "match_uid": match_data["match_uid"],
                "player_uid": player["player_uid"],
                "name": player["name"],
                "hero_id": player["hero_id"],
                "is_win": player["is_win"],
                "kills": player["kills"],
                "deaths": player["deaths"],
                "assists": player["assists"],
                "hero_damage": player["hero_damage"],
                "hero_healed": player["hero_healed"],
                "damage_taken": player["damage_taken"],
                "hero_data": f'"{hero_data_str}"',
            },
        )


# Parallel fetching of player details
def fetch_player_details_parallel(players_to_fetch):

    with ThreadPoolExecutor(max_workers=MAX_PARALLEL_REQUESTS) as executor:
        future_to_player = {
            executor.submit(fetch_and_process_player, player_id, timestamp, player_data): player_id
            for player_id, timestamp, player_data in players_to_fetch
        }

        for future in as_completed(future_to_player):
            player_id = future_to_player[future]
            try:
                future.result()
            except Exception as e:
                print(f"Error processing player {player_id}: {e}")



# Fetch and process a single player's data
def fetch_and_process_player(player_id, timestamp, leaderboard_entry):
    player_data = rate_limited_fetch(PLAYER_API_URL.format(player_id))
    
    is_private = player_data is None or player_data.get("is_profile_private", True)

    
    # Use R-friendly nil values
    rank_score = "NaN" if is_private else player_data["stats"]["rank"]["score"]
    player_name = "" if leaderboard_entry["player_name"] is None else leaderboard_entry["player_name"]
    rank_name = "" if leaderboard_entry["rank_name"] is None else leaderboard_entry["rank_name"]

    # Save leaderboard data, ensuring private profiles are logged
    append_csv(
        LEADERBOARD_FILE,
        ["timestamp", "rank", "player_name", "rank_name", "score", "matches", "player_id", "rank_score", "is_private"],
        {
            "timestamp": timestamp,
            "rank": leaderboard_entry["rank"],
            "player_name": player_name,
            "rank_name": rank_name,
            "score": leaderboard_entry["score"],
            "matches": leaderboard_entry["matches"],
            "player_id": player_id,
            "rank_score": rank_score,  # N/A if private
            "is_private": "Yes" if is_private else "No"
        },
    )

    # Process encountered players (teammates + match opponents)
    process_encountered_players(player_data, timestamp)



# Process teammates and match history
def process_encountered_players(player_data, timestamp):
    global total_scanned_matches, total_scanned_players
    if player_data.get("is_profile_private", True):
        return

    players_to_fetch = []
    matches_to_fetch = []

    # Process teammates
    if "teammates" in player_data:
        for teammate in player_data["teammates"]:
            if teammate["player_uid"] not in queried_players  # Avoid duplicate queries
                queried_players.add(teammate["player_uid"])
                players_to_fetch.append((teammate["player_uid"], timestamp))

    # Process match history (only fetch unique matches)
    if "match_history" in player_data:
        for match in player_data["match_history"]:
            match_id = match["match_uid"]
            if match_id not in queried_matches:
                queried_matches.add(match_id)
                matches_to_fetch.append(match_id)

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
    player_data = rate_limited_fetch(PLAYER_API_URL.format(player_id))

    is_private = player_data is None or player_data.get("is_profile_private", True)

    if is_private or player_data is None:
        return  # ✅ Exit early to prevent `.get()` errors
    
    # ✅ Use safe defaults for private profiles
    latest_score = player_data["stats"]["rank"].get("score", 0)
    matches = 0 if is_private else player_data["stats"].get("total_matches", 0)
    wins = 0 if is_private else player_data["stats"].get("total_wins", 0)
    player_name = player_data["player_name"]

    print(f"Processing encountered player {player_id} - {'PRIVATE' if is_private else 'PUBLIC'} profile...")
    with encountered_lock:
        # Check if the player already exists
        if player_id in encountered_players:
            encountered_players[player_id]["latest_score"] = latest_score
            encountered_players[player_id]["matches"] = matches
            encountered_players[player_id]["wins"] = wins
            # Update highest score if this is a new record
            if latest_score != 0 and latest_score > encountered_players[player_id]["highest_score"]:
                encountered_players[player_id]["highest_score"] = latest_score
        else:
            # Add new player
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
    if os.path.exists(MATCH_PLAYERS_FILE):
        old_match_players_data = pd.read_parquet(MATCH_PLAYERS_FILE, engine="pyarrow")
        combined_data = pd.concat([old_match_players_data, pd.DataFrame(match_players_data)])
        combined_data.drop_duplicates(subset=["match_uid", "player_uid"], keep="last", inplace=True)
    else:
        combined_data = pd.DataFrame(match_players_data)

    combined_data.to_parquet(MATCH_PLAYERS_FILE, index=False, engine="pyarrow")


if __name__ == "__main__":
    fetch_leaderboard()
    print(f"Saving {len(encountered_players)} encountered players to CSV...")
    save_encountered_players()
    save_to_disk()
    print("Data collection completed!")
    print(f"Total Players Scanned: {total_scanned_players}")
    print(f"Total Matches Scanned: {total_scanned_matches}")
    print(f"Private Profiles Encountered: {private_profile_count}")
