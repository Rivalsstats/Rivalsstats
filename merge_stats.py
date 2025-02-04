import json
import os
import csv
import sys
from datetime import datetime, timezone

user_to_check = sys.argv[1]  # Get the user ID from the command-line argument

# File paths (dynamic based on USER_TO_CHECK)
latest_file = f"data/latest/users/{user_to_check}.json"
stats_csv = f"data/historical/users/{user_to_check}/stats.csv"
rank_csv = f"data/historical/users/{user_to_check}/rank_history.csv"
match_csv = f"data/historical/users/{user_to_check}/match_history.csv"
hero_csv = f"data/historical/users/{user_to_check}/hero_matchups.csv"
teammates_csv = f"data/historical/users/{user_to_check}/teammates.csv"

# Load latest data
if os.path.exists(latest_file):
    with open(latest_file, "r", encoding="utf-8") as f:
        latest_data = json.load(f)
else:
    print("No latest data available.")
    exit()

os.makedirs(f"data/historical/users/{user_to_check}/", exist_ok=True)

def append_to_csv(data, filename, headers, row_formatter):
    """ Append new data to CSV, ensuring no duplicates. """
    file_exists = os.path.exists(filename)
    
    if not file_exists:
        with open(filename, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)  # Write headers if file is new

    existing_rows = set()
    if file_exists:
        with open(filename, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader, None)  # Skip header
            existing_rows = {tuple(row) for row in reader}

    new_rows = set(tuple(row_formatter(entry)) for entry in data) - existing_rows
    if new_rows:
        with open(filename, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            for row in new_rows:
                writer.writerow(row)

# Extract and append overall stats history
if "stats" in latest_data:
    timestamp = datetime.now(timezone.utc).isoformat()
    overall_stats = [
        [
            timestamp,
            latest_data["stats"]["ranked"].get("total_assists", 0),
            latest_data["stats"]["ranked"].get("total_deaths", 0),
            latest_data["stats"]["ranked"].get("total_kills", 0),
            latest_data["stats"]["ranked"].get("total_time_played", "0"),
            latest_data["stats"]["ranked"].get("total_matches", 0),
            latest_data["stats"]["ranked"].get("total_wins", 0),
            latest_data["stats"].get("total_matches", 0),
            latest_data["stats"].get("total_wins", 0),
            latest_data["stats"]["unranked"].get("total_assists", 0),
            latest_data["stats"]["unranked"].get("total_deaths", 0),
            latest_data["stats"]["unranked"].get("total_kills", 0),
            latest_data["stats"]["unranked"].get("total_time_played", "0"),
            latest_data["stats"]["unranked"].get("total_matches", 0),
            latest_data["stats"]["unranked"].get("total_wins", 0)
        ]
    ]
    
    append_to_csv(overall_stats, stats_csv, [
        "timestamp", "ranked_assists", "ranked_deaths", "ranked_kills", "ranked_time_played", 
        "ranked_matches", "ranked_matches_wins", "total_matches", "total_wins",
        "unranked_assists", "unranked_deaths", "unranked_kills", "unranked_time_played", 
        "unranked_matches", "unranked_matches_wins"
    ], lambda x: x)

# Extract and append rank history
if "rank_history" in latest_data:
    rank_history = [
        [
            entry["timestamp"], entry["rank"]["old_level"], entry["rank"]["new_level"],
            entry["rank"]["old_score"], entry["rank"]["new_score"]
        ]
        for entry in latest_data["rank_history"]
    ]
    append_to_csv(rank_history, rank_csv, ["timestamp", "from_level", "to_level", "old_score", "new_score"], lambda x: x)

# Extract and append match history
if "match_history" in latest_data:
    match_history = [
        (
            entry["match_uid"], entry["match_map"]["id"], entry["match_duration"]["raw"], entry["season"],
            entry["winner_side"], entry["mvp_uid"], entry["svp_uid"], entry["match_timestamp"], 
            entry["gamemode"]["id"], entry["stats"]["kills"], entry["stats"]["deaths"], entry["stats"]["assists"], 
            entry["stats"]["is_win"], entry["stats"]["hero"]["id"], entry["stats"]["has_escaped"]
        )
        for entry in latest_data["match_history"]
    ]
    append_to_csv(match_history, match_csv, [
        "match_uid", "map_id", "duration", "season", "winner_side", "mvp_uid", "svp_uid", "timestamp", 
        "game_mode_id", "kills", "deaths", "assists", "is_win", "hero_id", "has_escaped"
    ], lambda x: x)

# Extract and append hero matchup history
if "hero_stats" in latest_data:
    hero_matchups = [
        [timestamp, hero_id, hero_data["matchup"]["matches"], hero_data["matchup"]["wins"]]
        for hero_id, hero_data in latest_data["hero_stats"].items() if "matchup" in hero_data
    ]
    append_to_csv(hero_matchups, hero_csv, ["timestamp", "hero_id", "matches", "wins"], lambda x: x)

# Extract and append teammate history
if "teammates" in latest_data:
    team_mates = [
        [timestamp, entry["player_uid"], entry["stats"]["matches"], entry["stats"]["wins"]]
        for entry in latest_data["teammates"]
    ]
    append_to_csv(team_mates, teammates_csv, ["timestamp", "player_uid", "matches", "wins"], lambda x: x)

print("Latest data appended to CSV files.")
