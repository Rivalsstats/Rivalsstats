import json
import os
import sys
import csv
import asyncio
import aiohttp
from datetime import datetime

# Get hero slug from GitHub Actions job matrix
hero_slug = sys.argv[1]

# File paths
historical_json = f"data/historical/heroes/{hero_slug}.json"
meta_csv = f"data/historical/heroes/meta/{hero_slug}.csv"
leaderboard_csv = f"data/historical/heroes/leaderboard/{hero_slug}.csv"
latest_heroes_file = "data/latest/heroes/all_heroes.json"
latest_leaderboard_file = f"data/latest/heroes/latest_leaderboard_{hero_slug}.json"

# Ensure historical directory exists
os.makedirs("data/historical/heroes/meta", exist_ok=True)
os.makedirs("data/historical/heroes/leaderboard", exist_ok=True)

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

# Extract hero ID for API lookups
hero_id = hero_data.get("id")
if not hero_id:
    print(f"⚠️ Error: No hero ID found for {hero_slug}.")
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
    "latest_meta": hero_data.get("meta", []),  
    "latest_leaderboard": latest_leaderboard  
}

# Save latest JSON
with open(historical_json, "w", encoding="utf-8") as f:
    json.dump(historical_data, f, indent=4, ensure_ascii=False)

# Ensure CSV has headers
def ensure_csv_with_headers(file_path, headers):
    if not os.path.exists(file_path):
        with open(file_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)

# Ensure meta CSV exists with headers
ensure_csv_with_headers(meta_csv, ["timestamp", "hero_slug", "platform", "mode", "rank", "appearance_rate", "win_rate"])

# Ensure leaderboard CSV exists with headers (including extra fields)
leaderboard_headers = [
    "timestamp", "hero_slug", "rank", "player_name", "score", "matches", "player_id",
    "ranked_matches", "ranked_wins", "ranked_mvps", "ranked_svps", "ranked_kills",
    "ranked_deaths", "ranked_assists", "ranked_damage_given", "ranked_damage_received",
    "ranked_heal", "ranked_playtime", "matchup_matches", "matchup_wins"
]
ensure_csv_with_headers(leaderboard_csv, leaderboard_headers)

# Async function to fetch player stats
async def fetch_player_stats(session, player_id):
    url = f"https://mrapi.org/api/player/{player_id}"
    try:
        async with session.get(url, timeout=5) as response:
            if response.status == 200:
                return await response.json()
            else:
                print(f"⚠️ Error: API request failed for player {player_id} (Status {response.status})")
                return None
    except Exception as e:
        print(f"⚠️ Error: API request failed for player {player_id} ({e})")
        return None

# Async function to fetch all player stats in parallel
async def fetch_all_players(leaderboard):
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_player_stats(session, player["player_id"]) for player in leaderboard]
        return await asyncio.gather(*tasks)

# Fetch all player stats asynchronously
player_stats_list = asyncio.run(fetch_all_players(latest_leaderboard))

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
    
    for player, player_stats in zip(latest_leaderboard, player_stats_list):
        # Extract hero-specific stats
        ranked_stats = {}
        matchup_stats = {}

        if player_stats and "hero_stats" in player_stats:
            hero_stats = player_stats["hero_stats"].get(str(hero_id), {})  
            ranked_stats = hero_stats.get("ranked", {})
            matchup_stats = hero_stats.get("matchup", {})

        writer.writerow([
            timestamp,
            hero_slug,
            player["rank"],
            player["player_name"],
            player["score"],
            player["matches"],
            player["player_id"],
            ranked_stats.get("matches", 0),
            ranked_stats.get("wins", 0),
            ranked_stats.get("mvp", 0),
            ranked_stats.get("svp", 0),
            ranked_stats.get("kills", 0),
            ranked_stats.get("deaths", 0),
            ranked_stats.get("assists", 0),
            ranked_stats.get("damage_given", 0),
            ranked_stats.get("damage_received", 0),
            ranked_stats.get("heal", 0),
            ranked_stats.get("playtime", "0s"),
            matchup_stats.get("matches", 0),
            matchup_stats.get("wins", 0)
        ])

print(f"✅ Updated hero stats & leaderboard history for {hero_slug} (Stored in {meta_csv} & {leaderboard_csv}).")
