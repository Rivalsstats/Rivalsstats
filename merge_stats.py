import json
import os
from datetime import datetime

# Get the username dynamically from the environment variable
user_to_check = os.getenv("USER_TO_CHECK", "default_user")  # Fallback to "default_user" if not set

# File paths (dynamic based on USER_TO_CHECK)
historical_file = f"data/historical/{user_to_check}.json"
latest_file = "data/latest/latest.json"
output_file = f"data/historical/{user_to_check}_historical.json"  # The debug file

# Load historical data if it exists
if os.path.exists(historical_file):
    with open(historical_file, "r", encoding="utf-8") as f:
        historical_data = json.load(f)
else:
    historical_data = {}

# Load latest API data
with open(latest_file, "r", encoding="utf-8") as f:
    latest_data = json.load(f)

# Get current timestamp
timestamp = datetime.utcnow().isoformat()

def track_history(historical, key, new_value):
    """ Appends historical entries for stats while keeping current values. """
    if key not in historical:
        historical[key] = {"current": new_value, "historic": []}
    historical[key]["historic"].append({"timestamp": timestamp, "value": new_value})
    historical[key]["current"] = new_value

def merge_data(old, new):
    """ Merges new data into historical data while keeping historical values intact """

    # Preserve full player info
    old["player"] = new.get("player", old.get("player", {}))

    # Preserve and track overall stats
    if "overall_stats" in new:
        if "overall_stats" not in old:
            old["overall_stats"] = {}

        for stat, value in new["overall_stats"].items():
            if isinstance(value, dict):
                if stat not in old["overall_stats"]:
                    old["overall_stats"][stat] = {}

                for sub_stat, sub_value in value.items():
                    track_history(old["overall_stats"][stat], sub_stat, sub_value)
            else:
                track_history(old["overall_stats"], stat, value)

    # Append only new match history
    existing_match_ids = {match["match_uid"] for match in old.get("match_history", [])}
    new_matches = [match for match in new.get("match_history", []) if match["match_uid"] not in existing_match_ids]
    old.setdefault("match_history", []).extend(new_matches)

    # Track rank history
    existing_rank_timestamps = {entry["match_time_stamp"] for entry in old.get("rank_history", [])}
    new_rank_updates = [entry for entry in new.get("rank_history", []) if entry["match_time_stamp"] not in existing_rank_timestamps]
    old.setdefault("rank_history", []).extend(new_rank_updates)

    # Track hero matchups
    if "hero_matchups" in new:
        if "hero_matchups" not in old:
            old["hero_matchups"] = {}

        for matchup in new["hero_matchups"]:
            hero_id = matchup["hero_id"]
            if hero_id not in old["hero_matchups"]:
                old["hero_matchups"][hero_id] = {"current": matchup, "historic": []}

            old["hero_matchups"][hero_id]["historic"].append({
                "timestamp": timestamp,
                "matches": matchup["matches"],
                "wins": matchup["wins"]
            })
            old["hero_matchups"][hero_id]["current"] = matchup

    # Track teammates
    if "team_mates" in new:
        if "team_mates" not in old:
            old["team_mates"] = {}

        for teammate in new["team_mates"]:
            player_uid = teammate["player_info"]["player_uid"]
            if player_uid not in old["team_mates"]:
                old["team_mates"][player_uid] = {"current": teammate, "historic": []}

            old["team_mates"][player_uid]["historic"].append({
                "timestamp": timestamp,
                "matches": teammate["matches"],
                "wins": teammate["wins"]
            })
            old["team_mates"][player_uid]["current"] = teammate

    # Track ranked and unranked hero stats
    for category in ["heroes_ranked", "heroes_unranked"]:
        if category in new:
            if category not in old:
                old[category] = {}

            for hero in new[category]:
                hero_id = hero["hero_id"]
                if hero_id not in old[category]:
                    old[category][hero_id] = {"current": hero, "historic": []}

                old[category][hero_id]["historic"].append({
                    "timestamp": timestamp,
                    **{k: v for k, v in hero.items() if k != "hero_id"}
                })
                old[category][hero_id]["current"] = hero

    # Track maps data
    if "maps" in new:
        if "maps" not in old:
            old["maps"] = {}

        for map_data in new["maps"]:
            map_id = map_data["map_id"]
            if map_id not in old["maps"]:
                old["maps"][map_id] = {"current": map_data, "historic": []}

            old["maps"][map_id]["historic"].append({
                "timestamp": timestamp,
                "matches": map_data["matches"],
                "wins": map_data["wins"],
                "kills": map_data["kills"],
                "deaths": map_data["deaths"],
                "assists": map_data["assists"],
                "play_time": map_data["play_time"]
            })
            old["maps"][map_id]["current"] = map_data

    return old

# Merge the latest data into the historical dataset
updated_data = merge_data(historical_data, latest_data)

# Save updated data into the historical debug file
with open(output_file, "w", encoding="utf-8") as f:
    json.dump(updated_data, f, indent=4, ensure_ascii=False)

print(f"✅ Historical data written to {output_file}")
