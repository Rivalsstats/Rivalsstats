import json
import os
import csv
from datetime import datetime

# Get the username dynamically from the environment variable
user_to_check = os.getenv("USER_TO_CHECK", "default_user")  # Fallback to "default_user" if not set

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
    overall_stats = []
    for category, stats in latest_data["overall_stats"].items():
        if isinstance(stats, dict):
            for stat, value in stats.items():
                overall_stats.append([datetime.utcnow().isoformat(), category, stat, value])
    append_to_csv(overall_stats, stats_csv, ["timestamp", "category", "stat", "value"], lambda x: x)

# Extract and append rank history
if "rank_history" in latest_data:
    rank_history = [[entry["match_time_stamp"], entry["level_progression"]["from"], entry["level_progression"]["to"],
                     entry["score_progression"]["add_score"], entry["score_progression"]["total_score"]] 
                    for entry in latest_data["rank_history"]]
    append_to_csv(rank_history, rank_csv, ["timestamp", "from_level", "to_level", "score_added", "total_score"], lambda x: x)

# Extract and append match history
if "match_history" in latest_data:
    match_history = [[entry["match_uid"], entry["match_time_stamp"], entry["map_id"], entry["duration"], entry["season"],
                      entry["winner_side"], entry["player_performance"]["hero_id"], entry["player_performance"]["kills"],
                      entry["player_performance"]["deaths"], entry["player_performance"]["assists"],
                      entry["player_performance"]["score_change"], entry["player_performance"]["new_score"]] 
                     for entry in latest_data["match_history"]]
    append_to_csv(match_history, match_csv, ["match_uid", "timestamp", "map_id", "duration", "season", "winner_side", "hero_id", "kills", "deaths", "assists", "score_change", "new_score"], lambda x: x)

# Extract and append hero matchup history
if "hero_matchups" in latest_data:
    hero_matchups = [[datetime.utcnow().isoformat(), matchup["hero_id"], matchup["matches"], matchup["wins"]]
                     for matchup in latest_data["hero_matchups"]]
    append_to_csv(hero_matchups, hero_csv, ["timestamp", "hero_id", "matches", "wins"], lambda x: x)

# Extract and append teammate history
if "team_mates" in latest_data:
    team_mates = [[datetime.utcnow().isoformat(), teammate["player_info"]["player_uid"], teammate["matches"], teammate["wins"]]
                  for teammate in latest_data["team_mates"]]
    append_to_csv(team_mates, teammates_csv, ["timestamp", "player_uid", "matches", "wins"], lambda x: x)

print(f"Latest data appended to CSV files:")
print(f"- Stats: {stats_csv}")
print(f"- Rank History: {rank_csv}")
print(f"- Match History: {match_csv}")
print(f"- Hero Matchups: {hero_csv}")
print(f"- Teammates: {teammates_csv}")
