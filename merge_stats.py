import json
import os
import csv
from datetime import datetime

# Get the username dynamically from the environment variable
user_to_check = os.getenv("USER_TO_CHECK", "Jodsderechte")  # Default to the given user

# File paths (dynamic based on USER_TO_CHECK)
latest_file = f"data/latest/users/{user_to_check}.json"
stats_csv = f"data/historical/{user_to_check}/stats.csv"
rank_csv = f"data/historical/{user_to_check}/rank_history.csv"
match_csv = f"data/historical/{user_to_check}/match_history.csv"
hero_csv = f"data/historical/{user_to_check}/hero_matchups.csv"
teammates_csv = f"data/historical/{user_to_check}/teammates.csv"

# Load latest data
if os.path.exists(latest_file):
    with open(latest_file, "r", encoding="utf-8") as f:
        latest_data = json.load(f)
else:
    print("No latest data available.")
    exit()

os.makedirs(f"data/historical/{user_to_check}/", exist_ok=True)

def append_to_csv(data, filename, headers, row_formatter):
    """ Append new data to CSV, ensuring no duplicates. """
    existing_rows = set()
    if os.path.exists(filename):
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
if "overall_stats" in latest_data:
    timestamp = datetime.utcnow().isoformat()
    overall_stats = [
        [
            timestamp,
            latest_data["overall_stats"]["ranked"].get("total_assists", 0),
            latest_data["overall_stats"]["ranked"].get("total_deaths", 0),
            latest_data["overall_stats"]["ranked"].get("total_kills", 0),
            latest_data["overall_stats"]["ranked"].get("total_time_played", "0"),
            latest_data["overall_stats"].get("ranked_matches", 0),
            latest_data["overall_stats"].get("ranked_matches_wins", 0),
            latest_data["overall_stats"].get("total_matches", 0),
            latest_data["overall_stats"].get("total_wins", 0),
            latest_data["overall_stats"]["unranked"].get("total_assists", 0),
            latest_data["overall_stats"]["unranked"].get("total_deaths", 0),
            latest_data["overall_stats"]["unranked"].get("total_kills", 0),
            latest_data["overall_stats"]["unranked"].get("total_time_played", "0"),
            latest_data["overall_stats"].get("unranked_matches", 0),
            latest_data["overall_stats"].get("unranked_matches_wins", 0)
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
            entry["match_time_stamp"], entry["level_progression"]["from"], entry["level_progression"]["to"],
            entry["score_progression"]["add_score"], entry["score_progression"]["total_score"]
        ]
        for entry in latest_data["rank_history"]
    ]
    append_to_csv(rank_csv, rank_history, ["timestamp", "from_level", "to_level", "score_added", "total_score"], lambda x: x)

# Extract and append match history
if "match_history" in latest_data:
    match_history = [
        (
            entry["match_uid"], entry["map_id"], entry["duration"], entry["season"], entry["winner_side"],
            entry["mvp_uid"], entry["svp_uid"], entry["match_time_stamp"], entry["play_mode_id"], entry["game_mode_id"],
            entry["score_info"].get("0", 0), entry["score_info"].get("1", 0),
            entry["player_performance"]["player_uid"], entry["player_performance"]["hero_id"],
            entry["player_performance"]["kills"], entry["player_performance"]["deaths"],
            entry["player_performance"]["assists"], entry["player_performance"]["is_win"],
            entry["player_performance"]["has_escaped"], entry["player_performance"]["camp"],
            entry["player_performance"]["score_change"], entry["player_performance"]["level"],
            entry["player_performance"]["new_level"], entry["player_performance"]["new_score"]
        )
        for entry in latest_data["match_history"]
    ]
    append_to_csv(match_history, match_csv, [
        "match_uid", "map_id", "duration", "season", "winner_side", "mvp_uid", "svp_uid", "timestamp", 
        "play_mode_id", "game_mode_id", "score_team_0", "score_team_1", "player_uid", "hero_id", "kills", "deaths", 
        "assists", "is_win", "has_escaped", "camp", "score_change", "level", "new_level", "new_score"
    ], lambda x: x)

print("Latest data appended to CSV files.")
