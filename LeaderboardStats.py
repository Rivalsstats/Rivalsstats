import requests
import csv
import os
import datetime
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

# API Endpoints
LEADERBOARD_URL = "https://mrapi.org/api/leaderboard"
PLAYER_API_URL = "https://mrapi.org/api/player/{}"
MATCH_API_URL = "https://mrapi.org/api/match/{}"

# Filenames
LEADERBOARD_FILE = "data/historical/leaderboard.csv"
PLAYER_ENCOUNTERS_FILE = "data/historical/player_encounters.csv"
MATCHES_FILE = "data/historical/matches.csv"
MATCH_PLAYERS_FILE = "data/historical/match_players.csv"
# Constants
MAX_PARALLEL_REQUESTS = 10  # Keep this low to avoid hitting API limits
API_LIMIT = 500  # Max API calls per minute
API_DELAY = 60 / API_LIMIT  # Time per request to stay within limits

# Rate Limiting
request_count = 0
start_time = time.time()
lock = Lock()
private_profile_count = 0

# deduplication
queried_matches = load_existing_matches()  # Load past matches from file
queried_players = set()  # Stores already fetched player IDs

# stat collection

total_scanned_matches = 0
total_scanned_players = 0

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
    """Generic function to fetch JSON data with retries."""
    global private_profile_count
    for attempt in range(retries):
        try:
            response = requests.get(url)
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 500:
                print(f"Private profile detected: {url}")
                private_profile_count += 1
                return None  # Don't retry on 500
            print(f"Error {response.status_code} fetching {url}")
        except Exception as e:
            print(f"Exception fetching {url}: {e}")
        time.sleep(delay)
    return None


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
        append_csv(
            MATCH_PLAYERS_FILE,
            [
                "match_uid",
                "player_uid",
                "name",
                "hero_id",
                "is_win",
                "kills",
                "deaths",
                "assists",
                "hero_damage",
                "hero_healed",
                "damage_taken",
            ],
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
    
    # Default values for private profiles
    rank_score = "N/A"
    is_private = False

    if player_data:
        if player_data.get("is_profile_private", True):  # Profile is private
            print(f"Player {player_id} has a private profile. Logging with N/A values.")
            is_private = True
        else:  # Public profile, extract rank score
            rank_score = player_data["stats"]["rank"]["score"]

    # Save leaderboard data, ensuring private profiles are logged
    append_csv(
        LEADERBOARD_FILE,
        ["timestamp", "rank", "player_name", "rank_name", "score", "matches", "player_id", "rank_score", "is_private"],
        {
            "timestamp": timestamp,
            "rank": leaderboard_entry["rank"],
            "player_name": leaderboard_entry["player_name"],
            "rank_name": leaderboard_entry["rank_name"],
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
    if player_data.get("is_profile_private", True):
        return

    players_to_fetch = []
    matches_to_fetch = []

    # Process teammates
    if "teammates" in player_data:
        for teammate in player_data["teammates"]:
            if teammate["player_uid"] not in queried_players:  # Avoid duplicate queries
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
            executor.submit(fetch_and_process_teammate, player_id, timestamp): player_id
            for player_id, timestamp in players_to_fetch
        }

        for future in as_completed(future_to_teammate):
            player_id = future_to_teammate[future]
            try:
                future.result()
            except Exception as e:
                print(f"Error processing encountered player {player_id}: {e}")


# Fetch and process a single teammate's data
def fetch_and_process_teammate(player_id, timestamp):
    player_data = rate_limited_fetch(PLAYER_API_URL.format(player_id))
    if not player_data or player_data.get("is_profile_private", True):
        return

    print(f"Processing encountered player {player_data['player_name']} ({player_id})...")

    # Extract relevant stats
    player_name = player_data["player_name"]
    score = player_data["stats"]["rank"]["score"]
    total_matches = player_data["stats"]["total_matches"]
    total_wins = player_data["stats"]["total_wins"]

    # Save encountered player data
    append_csv(
        PLAYER_ENCOUNTERS_FILE,
        ["timestamp", "player_uid", "player_name", "score", "matches", "wins"],
        {
            "timestamp": timestamp,
            "player_uid": player_id,
            "player_name": player_name,
            "score": score,
            "matches": total_matches,
            "wins": total_wins
        },
    )
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

if __name__ == "__main__":
    fetch_leaderboard()
    print("Data collection completed!")
    print(f"Fetched a total of {total_scanned_players} Players and  {total_scanned_matches} Matches")
