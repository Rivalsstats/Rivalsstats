import json
import os
import sys
import csv
from datetime import datetime

# Get hero slug from GitHub Actions job matrix
hero_slug = sys.argv[1]

# File paths
historical_json = f"data/historical/heroes/{hero_slug}.json"  # Stores only latest stats
meta_csv = "data/historical/meta_history.csv"  # Stores historical hero stats
leaderboard_csv = "data/historical/leaderboard_history.csv"  # Stores leaderboard history
latest_heroes_file = "data/latest/heroes/latest_heroes.json"
latest_leaderboard_file = f"data/latest/heroes/latest_leaderboard_{hero_slug}.json"

# Ensure historical directory exists
os.makedirs("data/historical/heroes", exist_ok=True)

# Load latest hero data
if os.path.exists(latest_heroes_file):
    with open(latest_heroes_file, "r", encoding="utf-8") as f:
        latest_heroes = json.load(f)
else:
    print(f"⚠️ Error: {latest_heroes_file} not found.")
    sys.exit(1)

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

# Load existing JSON if available
if os.path.exists(historical_json):
    with open(historical_json, "r", encoding="utf-8") as f:
        historical_data = json.load(f)
else:
    historical_data = {}

# Update latest hero stats JSON
historical_data = {
    "name": hero_data["name"],
    "role": hero_data["role"],
    "latest_meta": hero_data.get("meta", []),  # Stores only current stats
    "latest_leaderboard": latest_leaderboard  # Stores only current leaderboard
}

# Save latest JSON
with open(historical_json, "w", encoding="utf-8") as f:
    json.dump(historical_data, f, indent=4, ensure_ascii=False)

# Append historical data to CSV files

# Save Hero Meta Data (Win Rate & Pick Rate)
with open(meta_csv, "a", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    for meta_entry in hero_data.get("meta", []):
        writer.writerow([
            timestamp,
            hero_slug,
            meta_entry["platform"],
            meta_entry["mode"],
            meta_entry["rank"],
            meta_entry["appearance_rate"],
            meta_entry["win_rate"]
        ])

# Save Leaderboard Data
with open(leaderboard_csv, "a", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    for player in latest_leaderboard:
        writer.writerow([
            timestamp,
            hero_slug,
            player["rank"],
            player["player_name"],
            player["score"],
            player["matches"],
            player["player_id"]
        ])

print(f"✅ Updated hero stats & leaderboard history for {hero_slug} (Stored in CSV).")
