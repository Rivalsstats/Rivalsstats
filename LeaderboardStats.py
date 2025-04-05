import requests
import csv
import os
import datetime
import time
import json
import threading
import pandas as pd
import pyarrow.parquet as pq
from queue import Queue

# API Endpoints
LEADERBOARD_URL = "https://rivalsmeta.com/api/leaderboard/data"

# Primary endpoints (using mrapi.org)
PLAYER_API_URL = "https://mrapi.org/api/player/{}"
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
MAX_PARALLEL_REQUESTS = 1  # Keep this low to avoid hitting API limits
DEFAULT_DELAY = 2  # Default delay between requests (in seconds)
headers = {"x-api-key": os.getenv("API_KEY_MRAPI")}
headers_rivals = {"x-api-key": os.getenv("API_KEY_RIVALS")}

# Define the timeout (5 hours)
TIMEOUT_SECONDS = 5 * 3600  # 5 hours
cancel_event = threading.Event()

# Queues
player_queue = Queue()
teammate_queue = Queue()
match_queue = Queue()
update_queue = Queue()

# holds extra info for matches
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
    
    print(f"[{datetime.datetime.now(datetime.timezone.utc).isoformat()}] Loaded {len(existing_matches)} existing matches from matches.csv.")
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
    print(f"[{datetime.datetime.now(datetime.timezone.utc).isoformat()}] Loaded {len(players)} existing encountered players.")
    return players


# deduplication
queried_matches = load_existing_matches()  # Load past matches from file
queried_players = set()  # Stores already fetched player IDs
encountered_players = load_existing_players()  # Load previously encountered players for teammates list
match_players_data = []
# stat collection

total_scanned_matches = 0
total_scanned_players = 0


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
    print(f"[{datetime.datetime.now(datetime.timezone.utc).isoformat()}] Fetching leaderboard data...")
    leaderboard, response_headers, status_code = fetchUrl(LEADERBOARD_URL)
    if not leaderboard:
        print(f"[{datetime.datetime.now(datetime.timezone.utc).isoformat()}] Failed to fetch leaderboard.")
        return

    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()

    for idx, player in enumerate(leaderboard["players"]):
        # Add rank based on the position in the leaderboard
        player["rank_in_leaderboard"] = idx + 1  
        player_id = player["uid"]
        if player_id not in queried_players:  # Only fetch if not already queried
            queried_players.add(player_id)
            if not cancel_event.is_set():
                player_queue.put((player_id, timestamp, player)) # enqueue players
    print(f"[{datetime.datetime.now(datetime.timezone.utc).isoformat()}] Processing {player_queue.qsize()} players from leaderboard...")

# process match details and save data
def process_match_data(match_id, match_data):
    """Fetch match details and save match/player data."""
    if not match_data or cancel_event.is_set():
        return
    print(f"[{datetime.datetime.now(datetime.timezone.utc).isoformat()}] Processing match {match_id}...")
    # Determine the structure used by the API:
    # If the response contains a "match_details" key, use that (backup format)
    if "match_details" in match_data:
        match_data = match_data["match_details"]
        # Use extra info from match_extra_info if available (e.g., for timestamp, season, map_id, etc.)
        extra = match_extra_info.get(match_id, {})
        csv_data = {
            "match_uid": match_data.get("match_uid", match_id),
            "replay_id": match_data.get("replay_id", ""),
            "gamemode": match_data.get("game_mode", {}).get("game_mode_name", "").lower(),
            "match_timestamp": extra.get("match_timestamp", ""),
            "mvp": match_data.get("mvp_uid", ""),
            "svp": match_data.get("svp_uid", ""),
            "season": str(int(str(extra.get("season", 0)).strip()) + 1) if str(extra.get("season", 0)).strip().isdigit() else "",
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
        standardized_match = standardize_match(match_data)
        json.dump(standardized_match, f)

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
    print(f"[{datetime.datetime.now(datetime.timezone.utc).isoformat()}] Match {match_id} succesfully processed") 


# Fetch and process a single player's data
def process_player(player_id, timestamp, leaderboard_entry,player_data):
    if cancel_event.is_set():
        return
    if not player_data or player_data == {}:  # Skip empty responses
        print(f"[{datetime.datetime.now(datetime.timezone.utc).isoformat()}]⚠️ Warning: No data returned for player {player_id}. Skipping...")
        return
    if not isinstance(player_data, dict):
        print(f"[{datetime.datetime.now(datetime.timezone.utc).isoformat()}]🚨 ERROR: Unexpected data type for player {player_id}. Got: {type(player_data)}")
        return
    
    os.makedirs("data/players", exist_ok=True)
    with open(os.path.join("data/players", f"{player_id}.json"), "w", encoding="utf-8") as f:
        standardized_player = standardize_player(player_data)
        json.dump(standardized_player, f)
    try:    
        # Determine if response is from primary or backup endpoint
        if "stats" in player_data:
            is_private = player_data.get("is_profile_private", True)
            rank_score = "NaN" if is_private else player_data.get("stats", {}).get("rank", {}).get("score", "NaN")
            player_name = player_data.get("player_name", "")
            rank_name = leaderboard_entry.get("rank_name", "")
        else:
            if "updates" in player_data:
                fields = ["last_history_update", "last_inserted_match", "last_update_request"]
                max_dt = None
                updates = player_data.get("updates", {})
                for field in fields:
                    ts_str = updates.get(field, "")
                    if ts_str:
                        try:
                            dt = datetime.datetime.strptime(ts_str, "%m/%d/%Y, %I:%M:%S %p").replace(tzinfo=datetime.timezone.utc)
                            if max_dt is None or dt > max_dt:
                                max_dt = dt
                        except Exception as e:
                            print(f"[{datetime.datetime.now(datetime.timezone.utc).isoformat()}] Error parsing {field} for player {player_id}: {e}")
                if max_dt is not None:
                    now = datetime.datetime.now(datetime.timezone.utc)
                    if (now - max_dt).total_seconds() > 24 * 3600:
                        print(f"[{datetime.datetime.now(datetime.timezone.utc).isoformat()}] Player {player_id} has not been updated in over 24 hours. requesting update...")
                        if not cancel_event.is_set():
                            update_queue.put(player_id) # enqueue players
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
        print(f"[{datetime.datetime.now(datetime.timezone.utc).isoformat()}] 🚨 ERROR: Exception while processing player {player_id}: {e}")
        print(f"[{datetime.datetime.now(datetime.timezone.utc).isoformat()}] Full player data: {json.dumps(player_data, indent=2)}")
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
        print(f"[{datetime.datetime.now(datetime.timezone.utc).isoformat()}] Error saving leaderboard data for player {player_id}: {e}")
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
    if cancel_event.is_set():
        return
    global total_scanned_matches, total_scanned_players
    if player_data.get("is_profile_private", player_data.get("isPrivate", True)):
        return

    # Process teammates
    if "teammates" in player_data:
        for teammate in player_data["teammates"]:
            pid = teammate.get("player_uid")
            if pid and pid not in queried_players:
                queried_players.add(pid)
                if not cancel_event.is_set():
                    teammate_queue.put((pid, timestamp)) # this is currently never processed, but could be in the future once ratelimits allow for it
    elif "team_mates" in player_data:
        for teammate in player_data["team_mates"]:
            pid = teammate.get("player_info", {}).get("player_uid")
            if pid and pid not in queried_players:
                queried_players.add(pid)
                if not cancel_event.is_set():
                    teammate_queue.put((pid, timestamp)) # this is currently never processed, but could be in the future once ratelimits allow for it

    # Process match history (only fetch unique matches)
    if "match_history" in player_data:
        for match in player_data["match_history"]:
            match_id = match.get("match_uid")
            if match_id and match_id not in queried_matches:
                queried_matches.add(match_id)
            
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
                if not cancel_event.is_set():
                    match_queue.put(match_id)
    else:
        print(f"[{datetime.datetime.now(datetime.timezone.utc).isoformat()}] Match history not found for player {player_data.get('player_uid', 'UNKNOWN')}")


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
    if cancel_event.is_set():
        return
    global encountered_players
    player_data = fetch_with_backup(None,
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
    
    print(f"[{datetime.datetime.now(datetime.timezone.utc).isoformat()}] Processing encountered player {player_id} - {'PRIVATE' if is_private else 'PUBLIC'} profile...")
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


def standardize_player(raw_player):
    if "updates" in raw_player:
        return standardize_player_backup(raw_player)
    else:
        return standardize_player_primary(raw_player)

def standardize_player_backup(raw_player):
    player_info = raw_player.get("player", {})
    return {
        "player_id": raw_player.get("uid", ""),
        "name": player_info.get("name", ""),
        "icon": player_info.get("icon", {}).get("player_icon", ""),
        "rank": player_info.get("rank", {}).get("rank", ""),
        "stats": raw_player.get("overall_stats", {}),
        "updates": raw_player.get("updates", {}),
        "match_history": [
            {
                "match_id": match.get("match_uid", ""),
                "map_id": match.get("map_id", ""),
                "season": str(int(str(match.get("season", 0)).strip()) + 1) if str(match.get("season", 0)).strip().isdigit() else "",
                "mvp_uid": match.get("mvp_uid", ""),
                "svp_uid": match.get("svp_uid", ""),
                "timestamp": match.get("match_time_stamp", ""),
                "duration": match.get("duration", 0),
                "result": "win" if match.get("winner_side", 0) == 1 else "loss",
                "disconnected": bool(match.get("player_performance", {}).get("disconnected", 0)),
                "score_change": match.get("player_performance", {}).get("score_change", 0),
                "new_score": match.get("player_performance", {}).get("new_score", 0),
                "is_win": bool(match.get("player_performance", {}).get("is_win",{}).get("is_win", 0)),
            }
            for match in raw_player.get("match_history", [])
        ],
        "team_mates": [
            {
                "player_id": tm.get("player_info", {}).get("player_uid", ""),
                "matches": tm.get("matches", 0),
                "wins": tm.get("wins", 0),
            }
            for tm in raw_player.get("team_mates", [])
        ],
        "hero_matchups": [
            {
                "hero_id": hm.get("hero_id", ""),
                "matches": hm.get("matches", 0),
                "wins": hm.get("wins", 0),
            }
            for hm in raw_player.get("hero_matchups", [])
        ],
        "heroes_ranked":[
            {
                "hero_id": hero.get("hero_id", ""),
                "matches": hero.get("matches", 0),
                "wins": hero.get("wins", 0),
                "mvp": hero.get("mvp", 0),
                "svp": hero.get("svp", 0),
                "kills": hero.get("kills", 0),
                "deaths": hero.get("deaths", 0),
                "assists": hero.get("assists", 0),
                "play_time": hero.get("play_time", 0),
                "damage": hero.get("damage", 0),
                "heal": hero.get("heal", 0),
                "damage_taken": hero.get("damage_taken", 0),
                "main_attack": hero.get("main_attack", 0),
            }
            for hero in raw_player.get("heroes_ranked", [])
        ],
        "heroes_unranked":[
            {
                "hero_id": hero.get("hero_id", ""),
                "matches": hero.get("matches", 0),
                "wins": hero.get("wins", 0),
                "mvp": hero.get("mvp", 0),
                "svp": hero.get("svp", 0),
                "kills": hero.get("kills", 0),
                "deaths": hero.get("deaths", 0),
                "assists": hero.get("assists", 0),
                "play_time": hero.get("play_time", 0),
                "damage": hero.get("damage", 0),
                "heal": hero.get("heal", 0),
                "damage_taken": hero.get("damage_taken", 0),
                "main_attack": hero.get("main_attack", 0),
            }
            for hero in raw_player.get("heroes_unranked", [])
        ],
        "maps":[
            {
               "map_id": map.get("map_id", ""),
               "matches": map.get("matches", 0),
               "wins": map.get("wins", 0),
               "kills": map.get("kills", 0),
               "deaths": map.get("deaths", 0),
               "assists": map.get("assists", 0),
               "play_time": map.get("play_time", 0),
            }
            for map in raw_player.get("maps", [])
        ],
    }

def standardize_player_primary(raw_player):
    # TODO IMPLEMENT THIS
    raise Exception(f"Primary endpoint player data has not been implemented yet. Player: {raw_player}")
    return {
        "todo": "Implement this function"
    }

def standardize_match(raw_match):
    # Determine API type by checking for key(s) unique to each format
    if "dynamic_fields" in raw_match:  # Backup API format
        return standardize_match_backup(raw_match)
    else:  # Primary API format
        return standardize_match_primary(raw_match)

def standardize_match_backup(raw_match):
    # Convert backup format to standard schema
    return {
        "match_id": raw_match.get("match_uid", ""),
        "replay_id": raw_match.get("replay_id", ""),
        "game_mode": raw_match.get("game_mode", {}).get("game_mode_name", ""),
        "mvp": {"player_id": raw_match.get("mvp_uid", ""), "hero_id": raw_match.get("mvp_hero_id", None)},
        "svp": {"player_id": raw_match.get("svp_uid", ""), "hero_id": raw_match.get("svp_hero_id", None)},
        "bans": [
            {
                "team": ban.get("battle_side", 0),
                "hero_id": ban.get("hero_id", ""),
            }
            for ban in raw_match.get("dynamic_fields", {}).get("ban_pick_info", [])
        ],
        "players": [standardize_match_player(p) for p in raw_match.get("match_players", [])]
    }

def standardize_match_primary(raw_match):
    # Convert primary format to standard schema
    # Adjust field names and nesting as needed
    raise Exception(f"Primary endpoint match data has not been implemented yet. Match {raw_match}")
    return {
        "todo": "Implement this function"
    }

def standardize_match_player(raw_player):
    return {
        "player_id": raw_player.get("player_uid", ""),
        "nickname": raw_player.get("nick_name", ""),
        "team": raw_player.get("camp", ""),
        "is_win": bool(raw_player.get("is_win", 0)),
        "damage_dealt": raw_player.get("total_hero_damage", 0),
        "healing": raw_player.get("total_hero_heal", 0),
        "damage_taken": raw_player.get("total_damage_taken", 0),
        "badges": raw_player.get("badges", []),
        "heroes": [
            {
                "hero_id": player_hero.get("hero_id", ""),
                "play_time": player_hero.get("play_time", 0),
                "kills": player_hero.get("kills", 0),
                "deaths": player_hero.get("deaths", 0),
                "assists": player_hero.get("assists", 0),
                "hit_rate": player_hero.get("session_hit_rate", 0),
            }
            for player_hero in  raw_player.get("player_heroes", [])
        ],
        
        
        
    }



def save_to_disk():
    """Writes all collected data to files in one batch."""
    df = pd.DataFrame(match_players_data)
    if "match_timestamp" not in df.columns or df.empty:
        print(f"[{datetime.datetime.now(datetime.timezone.utc).isoformat()}] No match_timestamp data found in match_players_data!")
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
            print(f"[{datetime.datetime.now(datetime.timezone.utc).isoformat()}] Saving group for week {week} of {year} to {filename}...")
            if os.path.exists(filename):
                old_data = pd.read_parquet(filename, engine="pyarrow")
                combined_group = pd.concat([old_data, group])
                combined_group.drop_duplicates(subset=["match_uid", "player_uid"], keep="last", inplace=True)
                combined_group.to_parquet(filename, index=False, engine="pyarrow")
            else:
                group.to_parquet(filename, index=False, engine="pyarrow")
    if not default_df.empty:
        default_filename = os.path.join(MATCH_PLAYERS_FILE, "match_players_default.parquet")
        print(f"[{datetime.datetime.now(datetime.timezone.utc).isoformat()}] Saving rows with missing timestamps to {default_filename}...")
        if os.path.exists(default_filename):
            old_data = pd.read_parquet(default_filename, engine="pyarrow")
            combined_default = pd.concat([old_data, default_df])
            combined_default.drop_duplicates(subset=["match_uid", "player_uid"], keep="last", inplace=True)
            combined_default.to_parquet(default_filename, index=False, engine="pyarrow")
        else:
            default_df.to_parquet(default_filename, index=False, engine="pyarrow")

def process_rate_limit(headers, source):
    print(f"[{datetime.datetime.now(datetime.timezone.utc).isoformat()}] Processing rate limit headers from {source}...")
    if headers.get("X-RateLimit-Remaining") is not None and headers.get("X-RateLimit-Remaining") != "Cache" and headers.get("X-RateLimit-Remaining") != "cache":
        rate_limit = headers.get("X-RateLimit-Limit")
        remaining = headers.get("X-RateLimit-Remaining")
        reset = headers.get("X-RateLimit-Reset")
        print(f"[{datetime.datetime.now(datetime.timezone.utc).isoformat()}] Backup API Rate Limit Info: Limit={rate_limit}, Remaining={remaining}, Reset={reset}")
        try:
            remaining_int = int(remaining) if remaining is not None else 1
            reset_int = int(reset) if reset is not None else 0
            if remaining_int <= 0:
                sleep_time = reset_int - int(time.time())
                if sleep_time > 0:
                    print(f"[{datetime.datetime.now(datetime.timezone.utc).isoformat()}] Rate limit reached. Sleeping for {sleep_time} seconds until reset.")
                    time.sleep(sleep_time)
        except Exception as e:
            print(f"[{datetime.datetime.now(datetime.timezone.utc).isoformat()}] Error processing rate limit headers: {e}")
    elif headers.get("X-RateLimit-Remaining") is not None and (headers.get("X-RateLimit-Remaining") == "Cache" or headers.get("X-RateLimit-Remaining") == "cache"):
        print(f"[{datetime.datetime.now(datetime.timezone.utc).isoformat()}] Cache rate limit headers detected. No need to rate limit")
    else:
        print(f"[{datetime.datetime.now(datetime.timezone.utc).isoformat()}]⚠️ Warning: Rate limit headers not found in response. {headers}")

def fetchUrl(url,headers=None):
    try:
        response = requests.get(url, headers=headers, timeout=30)
        # Detect Rate Limiting (429 Error)
        if response.status_code == 429:
            print(f"[{datetime.datetime.now(datetime.timezone.utc).isoformat()}]⚠️ Rate limit hit! on {url}: {response.text}")
            return None, response.headers, response.status_code
        elif response.status_code == 500:
            print(f"[{datetime.datetime.now(datetime.timezone.utc).isoformat()}]⚠️ Server error (500) on {url}: {response.text}")
            return None, response.headers, response.status_code
        # For any other API error (like 403)
        if response.status_code >= 400:
            print(f"[{datetime.datetime.now(datetime.timezone.utc).isoformat()}]⚠️ API Error {response.status_code} on {url}: {response.text}")
            return None, response.headers, response.status_code

        # Check for Non-JSON Responses
        if "application/json" not in response.headers.get("Content-Type", ""):
            print(f"[{datetime.datetime.now(datetime.timezone.utc).isoformat()}]⚠️ Warning: Non-JSON response from {url}. Skipping...")
            return None, None, response.status_code

        return response.json(), response.headers, response.status_code

    except requests.exceptions.RequestException as e:
        print(f"[{datetime.datetime.now(datetime.timezone.utc).isoformat()}]❌ Network error fetching {url}: {e}")
    except ValueError:
        print(f"[{datetime.datetime.now(datetime.timezone.utc).isoformat()}]⚠️ Invalid JSON response from {url}, skipping...")

def cancel_all_pending_tasks():
    print("5 hours elapsed. Cancelling all pending tasks...")
    cancel_and_flush_queue(player_queue, "player_queue")
    cancel_event.set()  # Signal cancellation
    time.sleep(60)  # Wait for 1 minute before cancelling other queues
    cancel_and_flush_queue(teammate_queue, "teammate_queue")
    cancel_and_flush_queue(match_queue, "match_queue")
    cancel_and_flush_queue(update_queue, "update_queue")

def cancel_and_flush_queue(q, queue_name="queue"):
    """Empty the given queue and add a sentinel so that the worker exits."""
    print(f"Cancelling pending tasks in {queue_name}.")
    while not q.empty():
        try:
            q.get_nowait()
            q.task_done()
        except Exception as e:
            print(f"[{datetime.datetime.now(datetime.timezone.utc).isoformat()}] Nerror canceling queue {queue_name}: {e}")
            break
    # Enqueue a sentinel to unblock the consumer.
    q.put(None)

def player_worker():
    while True:
        try:
            # Try to get a task; timeout after 5 seconds if the queue is empty.
            task = player_queue.get(timeout=10)
        except Exception:
            print(f"[{datetime.datetime.now(datetime.timezone.utc).isoformat()}] No more players to process. Exiting...")
            player_queue.task_done()
            break  # Exit loop if no task is received within the timeout.
        if task is None or cancel_event.is_set():
            player_queue.task_done()
            break
        try:
            player_id, timestamp, leaderboard_entry = task
            print(f"[{datetime.datetime.now(datetime.timezone.utc).isoformat()}] Fetching player {player_id}...({player_queue.qsize()} left)")
            response, resulting_headers, status_code = fetchUrl(PLAYER_API_URL_RIVALS.format(player_id),headers_rivals)
            process_rate_limit(resulting_headers, "player")
            if status_code == 429:
                if not cancel_event.is_set():
                    player_queue.put((player_id, timestamp, leaderboard_entry))
            process_player(player_id, timestamp, leaderboard_entry, response)
        except Exception as e:
            print(f"[{datetime.datetime.now(datetime.timezone.utc).isoformat()}] Error processing player {player_id}: {e}")
        finally:
            player_queue.task_done()


def teammate_worker():
    while True:
        task = teammate_queue.get()
        if task is None or cancel_event.is_set():
            teammate_queue.task_done()
            break
        player_id, timestamp = task
        try:
            fetch_and_process_teammate(player_id)
        except Exception as e:
            print(f"[{datetime.datetime.now(datetime.timezone.utc).isoformat()}] Error processing teammate {player_id}: {e}")
        finally:
            teammate_queue.task_done()

def match_worker():
    while True:
        # Block indefinitely until a task is available.
        match_id = match_queue.get()
        # If we get a sentinel (None), then break out of the loop.
        if match_id is None or cancel_event.is_set():
            match_queue.task_done()
            break
        try:
            print(f"[{datetime.datetime.now(datetime.timezone.utc).isoformat()}] Fetching match {match_id}... ({match_queue.qsize()} left)")
            response, resulting_headers, status_code = fetchUrl(MATCH_API_URL_RIVALS.format(match_id),headers_rivals)
            process_rate_limit(resulting_headers , "match")
            if status_code == 429:
                if not cancel_event.is_set():
                    match_queue.put(match_id)
            process_match_data(match_id, response)
        except Exception as e:
            print(f"[{datetime.datetime.now(datetime.timezone.utc).isoformat()}] Error processing match {match_id}: {e}")
        finally:
            match_queue.task_done()


def update_worker():
    while True:
        # Block indefinitely until a task is available.
        player_id = update_queue.get()
        # If we get a sentinel (None), then break out of the loop.
        if player_id is None or cancel_event.is_set():
            update_queue.task_done()

            break
        try:
            if cancel_event.is_set():
                break
            print(f"[{datetime.datetime.now(datetime.timezone.utc).isoformat()}] Fetching player update {player_id}... ({update_queue.qsize()} left)")
            response, resulting_headers, status_code = fetchUrl(PLAYER_API_URL_RIVALS.format(player_id),headers_rivals)
            process_rate_limit(resulting_headers, "update")
            if status_code == 429:
                if not cancel_event.is_set():
                    update_queue.put(player_id)
        except Exception as e:
            print(f"[{datetime.datetime.now(datetime.timezone.utc).isoformat()}] Error processing player {player_id}: {e}")
        finally:
            update_queue.task_done()

if __name__ == "__main__":
    print(f"[{datetime.datetime.now(datetime.timezone.utc).isoformat()}] Starting data collection...")
    cancel_timer = threading.Timer(TIMEOUT_SECONDS, cancel_all_pending_tasks)
    cancel_timer.start()
    print(f"[{datetime.datetime.now(datetime.timezone.utc).isoformat()}] Started cancel timer for {TIMEOUT_SECONDS} seconds.")
    fetch_leaderboard()
    # Start consumer worker threads for each queue.
    player_thread = threading.Thread(target=player_worker)
    match_thread = threading.Thread(target=match_worker)
    update_thread = threading.Thread(target=update_worker)
    #teammate_thread = threading.Thread(target=teammate_worker)

    player_thread.start()
    #teammate_thread.start()
    match_thread.start()
    update_thread.start()

    # Wait for all player tasks to finish.
    print(f"[{datetime.datetime.now(datetime.timezone.utc).isoformat()}] Waiting for Player queue to finish...")
    player_queue.join()
    print(f"[{datetime.datetime.now(datetime.timezone.utc).isoformat()}] Player thread finished. Still waiting for {match_queue.qsize()} matches to finish...")
    # Now that all players are processed, no new match/teammate tasks will be added.
    # Signal the match and teammate workers to exit by enqueuing a sentinel.
    if not cancel_event.is_set():
        match_queue.put(None)
        update_queue.put(None)
    #teammate_queue.put(None)
    print(f"[{datetime.datetime.now(datetime.timezone.utc).isoformat()}] Waiting for queues to finish...")
    # Wait for match and teammate queues to be processed.
    match_queue.join()
    print(f"[{datetime.datetime.now(datetime.timezone.utc).isoformat()}] Match queue finished")
    update_queue.join()
    print(f"[{datetime.datetime.now(datetime.timezone.utc).isoformat()}] Update queue finished")
    #teammate_queue.join()
    cancel_timer.cancel()
    print(f"[{datetime.datetime.now(datetime.timezone.utc).isoformat()}] Cancel timer cancelled.")

    # wait for worker threads to finish
    print(f"[{datetime.datetime.now(datetime.timezone.utc).isoformat()}] Waiting for threads to finish...")
    player_thread.join()
    match_thread.join()
    update_thread.join()
    #teammate_thread.join()
    print(f"[{datetime.datetime.now(datetime.timezone.utc).isoformat()}] Data collection completed!")
    save_encountered_players()
    save_to_disk()
    print(f"[{datetime.datetime.now(datetime.timezone.utc).isoformat()}] Total Players Scanned: {total_scanned_players}")
    print(f"[{datetime.datetime.now(datetime.timezone.utc).isoformat()}] Total Matches Scanned: {total_scanned_matches}")
