import requests
import csv
import os
import datetime
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

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
    for attempt in range(retries):
        try:
            response = requests.get(url)
            if response.status_code == 200:
                return response.json()
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
    seen_players = set()  # Track players to prevent duplicate entries

    print(f"Processing {len(leaderboard)} players from leaderboard...")

    players_to_fetch = []

    for player in leaderboard:
        player_id = player["player_id"]

        # Queue player for fetching details
        players_to_fetch.append((player_id, timestamp, player, seen_players))

    # Fetch all player details in parallel
    fetch_player_details_parallel(players_to_fetch)


# Parallel fetching of player details
def fetch_player_details_parallel(players_to_fetch):
    print(f"Fetching details for {len(players_to_fetch)} players...")

    with ThreadPoolExecutor(max_workers=MAX_PARALLEL_REQUESTS) as executor:
        future_to_player = {
            executor.submit(fetch_and_process_player, player_id, timestamp, player_data, seen_players): player_id
            for player_id, timestamp, player_data, seen_players in players_to_fetch
        }

        for future in as_completed(future_to_player):
            player_id = future_to_player[future]
            try:
                future.result()
            except Exception as e:
                print(f"Error processing player {player_id}: {e}")


# Fetch and process a single player's data
def fetch_and_process_player(player_id, timestamp, leaderboard_entry, seen_players):
    player_data = rate_limited_fetch(PLAYER_API_URL.format(player_id))
    if not player_data:
        return

    print(f"Processing player {player_data['player_name']} ({player_id})...")

    # Extract rank score (if available)
    rank_score = None
    if not player_data.get("is_profile_private", True):
        rank_score = player_data["stats"]["rank"]["score"]

    # Save leaderboard data with rank score
    append_csv(
        LEADERBOARD_FILE,
        ["timestamp", "rank", "player_name", "rank_name", "score", "matches", "player_id", "rank_score"],
        {
            "timestamp": timestamp,
            "rank": leaderboard_entry["rank"],
            "player_name": leaderboard_entry["player_name"],
            "rank_name": leaderboard_entry["rank_name"],
            "score": leaderboard_entry["score"],
            "matches": leaderboard_entry["matches"],
            "player_id": player_id,
            "rank_score": rank_score
        },
    )

    # Save encountered players (teammates + match opponents)
    process_encountered_players(player_data, timestamp, seen_players)


# Process teammates and match history
def process_encountered_players(player_data, timestamp, seen_players):
    if player_data.get("is_profile_private", True):
        return

    players_to_fetch = []

    # Process teammates
    if "teammates" in player_data:
        for teammate in player_data["teammates"]:
            players_to_fetch.append((teammate["player_uid"], timestamp, seen_players))

    # Fetch teammates' details in parallel
    fetch_teammates_parallel(players_to_fetch)

    # Process match history
    if "match_history" in player_data:
        for match in player_data["match_history"]:
            match_id = match["match_uid"]
            fetch_match_data(match_id)


# Fetch teammates' details in parallel
def fetch_teammates_parallel(players_to_fetch):
    if not players_to_fetch:
        return

    print(f"Fetching details for {len(players_to_fetch)} encountered players...")

    with ThreadPoolExecutor(max_workers=MAX_PARALLEL_REQUESTS) as executor:
        future_to_teammate = {
            executor.submit(fetch_and_process_teammate, player_id, timestamp, seen_players): player_id
            for player_id, timestamp, seen_players in players_to_fetch
        }

        for future in as_completed(future_to_teammate):
            player_id = future_to_teammate[future]
            try:
                future.result()
            except Exception as e:
                print(f"Error processing encountered player {player_id}: {e}")


# Fetch and process a single teammate's data
def fetch_and_process_teammate(player_id, timestamp, seen_players):
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
        seen_entries=seen_players
    )


if __name__ == "__main__":
    fetch_leaderboard()
    print("Data collection completed!")
