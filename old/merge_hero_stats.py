import json
import os
from datetime import datetime

# File paths
historical_file = "data/heroes_historical.json"
latest_file = "data/latest_heroes.json"

# Load historical hero data if it exists
if os.path.exists(historical_file):
    with open(historical_file, "r", encoding="utf-8") as f:
        historical_data = json.load(f)
else:
    historical_data = {}

# Load latest API hero data
with open(latest_file, "r", encoding="utf-8") as f:
    latest_data = json.load(f)

# Get current timestamp
timestamp = datetime.utcnow().isoformat()

# Merge logic
def merge_heroes(historical, latest):
    """ Merge latest hero data into historical data while keeping track of changes over time. """

    for category, heroes in latest.items():
        if category not in historical:
            historical[category] = {}

        for hero in heroes:
            hero_name = hero["name"]

            if hero_name not in historical[category]:
                # Create a new hero entry with a history list
                historical[category][hero_name] = {
                    "role": hero["role"],
                    "history": []
                }

            # Append the latest stats with a timestamp
            historical[category][hero_name]["history"].append({
                "timestamp": timestamp,
                "pickRate": hero["pickRate"],
                "winRate": hero["winRate"]
            })

    return historical

# Merge the latest hero data into the historical dataset
updated_heroes = merge_heroes(historical_data, latest_data)

# Save updated data into the historical debug file
with open(historical_file, "w", encoding="utf-8") as f:
    json.dump(updated_heroes, f, indent=4, ensure_ascii=False)

print(f"Historical hero data written to {historical_file} for debugging.")
