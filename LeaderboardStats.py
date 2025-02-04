import requests
import csv
import os
import datetime
import time

# API Endpoints
LEADERBOARD_URL = "https://mrapi.org/api/leaderboard"
PLAYER_API_URL = "https://mrapi.org/api/player/{}"
MATCH_API_URL = "https://mrapi.org/api/match/{}"

# Filenames
LEADERBOARD_FILE = "leaderboard.csv"
PLAYER_ENCOUNTERS_FILE = "player_encounters.csv"
MATCHES_FILE = "matches.csv"
MATCH_PLAYERS_FILE = "match_players.csv"

# Function to fetch JSON data with retries
def fetch_data(url, retries=3, delay=2):
    for attempt in range(retries):
        try:
            response = requests.get(url)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"Error fetching {url}: {e}")
        time.sleep(delay)
    return None

# Function to append new rows to a CSV file
def append_csv(filename, fieldnames, data):
    file_exists = os.path.isfile(filename)
    with open(filename, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow(data)

# Fetch leaderboard
def fetch_leaderboard():
    leaderboard = fetch_data(LEADERBOARD_URL)
    if not leaderboard:
        print("Failed to fetch leaderboard.")
        return

    timestamp = datetime.datetime.utcnow().isoformat()
    
    for player in leaderboard:
        player_id = player["player_id"]
        rank_score = None

        # Fetch player details
        player_data = fetch_data(PLAYER_API_URL.format(player_id))
        if player_data and not player_data.get("is_profile_private", True):
            rank_score = player_data["stats"]["rank"]["score"]
        
        # Append leaderboard data
        append_csv(LEADERBOARD_FILE, 
            ["timestamp", "rank", "player_name", "rank_name", "score", "matches", "player_id", "rank_score"], 
            {
                "timestamp": timestamp,
                "rank": player["rank"],
                "player_name": player["player_name"],
                "rank_name": player["rank_name"],
                "score": player["score"],
                "matches": player["matches"],
                "player_id": player_id,
                "rank_score": rank_score
            }
        )

        # Process encountered players (teammates + match history)
        if player_data and not player_data.get("is_profile_private", True):
            process_encountered_players(player_data, timestamp)

# Fetch and store encountered players
def process_encountered_players(player_data, timestamp):
    player_id = player_data["player_uid"]
    
    # Process teammates
    if "teammates" in player_data:
        for teammate in player_data["teammates"]:
            append_csv(PLAYER_ENCOUNTERS_FILE, 
                ["timestamp", "player_uid", "player_name"], 
                {
                    "timestamp": timestamp,
                    "player_uid": teammate["player_uid"],
                    "player_name": teammate["name"]
                }
            )
    
    # Process match history
    if "match_history" in player_data:
        for match in player_data["match_history"]:
            match_id = match["match_uid"]
            fetch_match_data(match_id)

# Fetch match details and save data
def fetch_match_data(match_id):
    match_data = fetch_data(MATCH_API_URL.format(match_id))
    if not match_data:
        return

    # Save match details
    append_csv(MATCHES_FILE, 
        ["match_uid", "replay_id", "gamemode"], 
        {
            "match_uid": match_data["match_uid"],
            "replay_id": match_data["replay_id"],
            "gamemode": match_data["gamemode"]["name"]
        }
    )

    # Save match players
    for player in match_data["players"]:
        append_csv(MATCH_PLAYERS_FILE, 
            ["match_uid", "player_uid", "name", "hero_id", "is_win", "kills", "deaths", "assists", "hero_damage", "hero_healed", "damage_taken"], 
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
                "damage_taken": player["damage_taken"]
            }
        )

if __name__ == "__main__":
    fetch_leaderboard()
