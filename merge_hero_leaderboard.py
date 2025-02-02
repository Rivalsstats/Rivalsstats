import json
import os
import sys
from datetime import datetime

# Get hero slug from GitHub Actions job matrix
hero_slug = sys.argv[1]

# File paths
historical_file = "data/heroes_historical.json"
latest_heroes_file = "data/latest_heroes.json"
latest_leaderboard_file = f"data/latest_leaderboard_{hero_slug}.json"

# Load existing historical data
if os.path.exists(historical_file):
    with open(historical_file, "r", encoding="utf-8") as f:
        historical_data = json.load(f)
else:
    historical_data = {}

# Load latest hero data
with open(latest_heroes_file, "r", encoding="utf-8") as f:
    latest_heroes = json.load(f)

# Find the specific hero
hero_data = next((h for h in latest_heroes if h["slug"] == hero_slug), None)

# Load latest leaderboard data
if os.path.exists(latest_leaderboard_file):
    with open(latest_leaderboard_file, "r", encoding="utf-8") as f:
        latest_leaderboard = json.load(f)
else:
    latest_leaderboard = []

# Get timestamp
timestamp = datetime.utcnow().isoformat()

# Update hero stats
if hero_data:
    if hero_slug not in historical_data:
        historical_data[hero_slug] = {
            "name": hero_data["name"],
            "role": hero_data["role"],
            "meta_history": [],
            "leaderboard_history": []
        }

    # Append latest hero meta stats (win rates & pick rates)
    for meta_entry in hero_data.get("meta", []):
        historical_data[hero_slug]["meta_history"].append({
            "timestamp": timestamp,
            "platform": meta_entry["platform"],
            "mode": meta_entry["mode"],
            "rank": meta_entry["rank"],
            "appearance_rate": meta_entry["appearance_rate"],
            "win_rate": meta_entry["win_rate"]
        })

    # Append latest leaderboard data
    historical_data[hero_slug]["leaderboard_history"].append({
        "timestamp": timestamp,
        "top_players": latest_leaderboard
    })

# Save updated historical data
with open(historical_file, "w", encoding="utf-8") as f:
    json.dump(historical_data, f, indent=4, ensure_ascii=False)

print(f"✅ Updated hero stats & leaderboard history for {hero_slug}")
