import json
import os

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

# Merge logic
def merge_data(old, new):
    """ Merges new data into historical data while keeping historical values intact """

    # Update player info
    old["player"] = new["player"]

    # Update overall stats
    old["overall_stats"] = new["overall_stats"]

    # Append only new match history
    existing_match_ids = {match["match_uid"] for match in old.get("match_history", [])}
    new_matches = [match for match in new.get("match_history", []) if match["match_uid"] not in existing_match_ids]
    old.setdefault("match_history", []).extend(new_matches)

    # Update rank history, appending only new rank progressions
    existing_rank_timestamps = {entry["match_time_stamp"] for entry in old.get("rank_history", [])}
    new_rank_updates = [entry for entry in new.get("rank_history", []) if entry["match_time_stamp"] not in existing_rank_timestamps]
    old.setdefault("rank_history", []).extend(new_rank_updates)

    return old

# Merge the latest data into the historical dataset
updated_data = merge_data(historical_data, latest_data)

# Save updated data into the historical debug file
with open(output_file, "w", encoding="utf-8") as f:
    json.dump(updated_data, f, indent=4, ensure_ascii=False)

print(f"Historical data written to {output_file} for debugging.")
