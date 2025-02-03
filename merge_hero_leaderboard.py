import json
import os
import sys
import csv
from datetime import datetime
import requests

# Get hero slug from command-line arguments
hero_slug = sys.argv[1]

# File paths
historical_json = f"data/historical/heroes/{hero_slug}.json"  # Stores only latest stats
meta_csv = f"data/historical/heroes/meta_history_{hero_slug}.csv"  # Hero-specific meta history
leaderboard_csv = f"data/historical/heroes/leaderboard_history_{hero_slug}.csv"  # Hero-specific leaderboard history
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
if not hero_data:
    print(f"⚠️ Error: No hero data found for slug {hero_slug}.")
    sys.exit(1)

# Retrieve hero ID from hero_data
hero_id = hero_data.get("id")
if not hero_id:
    print(f"⚠️ Error: No hero ID found for slug {hero_slug}.")
    sys.exit(1)

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

# Check if CSV files exist, if not, add headers
def ensure_csv_with_headers(file_path, headers):
    if not os.path.exists(file_path):
        with open(file_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)

# Ensure meta CSV exists with headers
ensure_csv_with_headers(meta_csv, ["timestamp", "hero_slug", "platform", "mode", "rank", "appearance_rate", "win_rate"])

# Ensure leaderboard CSV exists with headers
leaderboard_headers = [
    "timestamp", "hero_slug", "rank", "player_name", "score", "matches", "player_id",
    "ranked_matches", "ranked_wins", "ranked_mvps", "ranked_svps", "ranked_kills",
    "ranked_deaths", "ranked_assists", "ranked_damage_given", "ranked_damage_received",
    "ranked_heal", "ranked_playtime", "matchup_matches", "matchup_wins"
]
ensure_csv_with_headers(leaderboard_csv, leaderboard_headers)

# Function to fetch player data from API
def fetch_player_data(player_id):
    api_url = f"https://mrapi.org/api/player/{player_id}"
    try:
        response = requests.get(api_url)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"⚠️ Error fetching data for player {player_id}: {e}")
        return None

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

# Save Leaderboard Data with additional player stats
with open(leaderboard_csv, "a", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    for player in latest_leaderboard:
        player_id = player["player_id"]
        player_data = fetch_player_data(player_id)
        
        # Initialize additional stats
        ranked_stats = {
            "matches": None, "wins": None, "mvp": None, "svp": None, "kills": None,
            "deaths": None, "assists": None, "damage_given": None, "damage_received": None,
            "heal": None, "playtime": None
        }
        matchup_stats = {"matches": None, "wins": None}

        if player_data and "hero_stats" in player_data and str(hero_id) in player_data["hero_stats"]:
            hero_stats = player_data["hero_stats"][str(hero_id)]
            ranked_stats.update(hero_stats.get("ranked", {}))
            matchup_stats.update(hero_stats.get("matchup", {}))

        writer.writerow([
            timestamp,
            hero_slug,
            player["rank"],
            player["player_name"],
            player["score"],
            player["matches"],
            player_id,
            ranked_stats["matches"],
            ranked_stats["wins"],
            ranked_stats["mvp"],
            ranked_stats["svp"],
            ranked_stats["kills"],
            ranked_stats["deaths"],
            ranked_stats["assists"],
            ranked_stats["damage_given"],
            ranked_stats["damage_received"],
            ranked_stats["heal"],
            ranked_stats["playtime"],
            matchup_stats["matches"],
            matchup_stats["
::contentReference[oaicite:0]{index=0}
 
