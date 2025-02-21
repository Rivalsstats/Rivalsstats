import json
import csv
import os
from datetime import datetime, timezone

# Define file paths
historical_file = "data/historical/users/Jodsderechte_historical.json"  # Change to your actual path
output_dir = "data/historical/users/csv_output"

# Ensure output directory exists
os.makedirs(output_dir, exist_ok=True)

# Output CSV files
stats_csv = os.path.join(output_dir, "stats.csv")
rank_csv = os.path.join(output_dir, "rank_history.csv")
match_csv = os.path.join(output_dir, "match_history.csv")
hero_csv = os.path.join(output_dir, "hero_matchups.csv")
teammates_csv = os.path.join(output_dir, "teammates.csv")

# Load historical JSON data
if os.path.exists(historical_file):
    with open(historical_file, "r", encoding="utf-8") as f:
        historical_data = json.load(f)
else:
    print("No historical data file found.")
    exit()

def save_to_csv(data, filename, headers, row_formatter):
    """ Saves extracted data to a CSV file """
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for entry in data:
            writer.writerow(row_formatter(entry))

# Extract and append overall stats history
if "overall_stats" in historical_data:
    timestamp = datetime.now(timezone.utc).isoformat()
    overall_stats = [
        [
            timestamp,
            historical_data["overall_stats"]["ranked"].get("total_assists", 0),
            historical_data["overall_stats"]["ranked"].get("total_deaths", 0),
            historical_data["overall_stats"]["ranked"].get("total_kills", 0),
            historical_data["overall_stats"]["ranked"].get("total_time_played", "0"),
            historical_data["overall_stats"].get("ranked_matches", 0),
            historical_data["overall_stats"].get("ranked_matches_wins", 0),
            historical_data["overall_stats"].get("total_matches", 0),
            historical_data["overall_stats"].get("total_wins", 0),
            historical_data["overall_stats"]["unranked"].get("total_assists", 0),
            historical_data["overall_stats"]["unranked"].get("total_deaths", 0),
            historical_data["overall_stats"]["unranked"].get("total_kills", 0),
            historical_data["overall_stats"]["unranked"].get("total_time_played", "0"),
            historical_data["overall_stats"].get("unranked_matches", 0),
            historical_data["overall_stats"].get("unranked_matches_wins", 0)
        ]
    ]
    
    save_to_csv(overall_stats, stats_csv, [
        "timestamp", "ranked_assists", "ranked_deaths", "ranked_kills", "ranked_time_played", 
        "ranked_matches", "ranked_matches_wins", "total_matches", "total_wins",
        "unranked_assists", "unranked_deaths", "unranked_kills", "unranked_time_played", 
        "unranked_matches", "unranked_matches_wins"
    ], lambda x: x)

# Extract and save rank history
if "rank_history" in historical_data:
    rank_history = [
        (entry["match_time_stamp"], entry["level_progression"]["from"], entry["level_progression"]["to"],
         entry["score_progression"]["add_score"], entry["score_progression"]["total_score"])
        for entry in historical_data["rank_history"]
    ]
    save_to_csv(rank_history, rank_csv, ["timestamp", "from_level", "to_level", "score_added", "total_score"], lambda x: x)

# Extract and save match history
if "match_history" in historical_data:
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
        for entry in historical_data["match_history"]
    ]
    save_to_csv(match_history, match_csv, ["match_uid", "map_id", "duration", "season", "winner_side", "mvp_uid", "svp_uid", "timestamp", "play_mode_id", "game_mode_id", "score_team_0", "score_team_1", "player_uid", "hero_id", "kills", "deaths", "assists", "is_win", "has_escaped", "camp", "score_change", "level", "new_level", "new_score"], lambda x: x)

# Extract and save hero matchup history
if "hero_matchups" in historical_data:
    hero_matchups = [
        (record["timestamp"], hero_id, record["matches"], record["wins"])
        for hero_id, data in historical_data["hero_matchups"].items()
        for record in data.get("historic", [])
    ]
    save_to_csv(hero_matchups, hero_csv, ["timestamp", "hero_id", "matches", "wins"], lambda x: x)

# Extract and save teammate history
if "team_mates" in historical_data:
    team_mates = [
        (record["timestamp"], player_uid, record["matches"], record["wins"])
        for player_uid, data in historical_data["team_mates"].items()
        for record in data.get("historic", [])
    ]
    save_to_csv(team_mates, teammates_csv, ["timestamp", "player_uid", "matches", "wins"], lambda x: x)

print("Conversion complete! CSV files saved in:", output_dir)
