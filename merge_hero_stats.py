import json
import os

# File paths
historical_file = "data/heroes.json"
latest_file = "data/latest_heroes.json"
output_file = "data/heroes_historical.json"  # Debug version

# Load historical hero data if it exists
if os.path.exists(historical_file):
    with open(historical_file, "r", encoding="utf-8") as f:
        historical_data = json.load(f)
else:
    historical_data = {}

# Load latest API hero data
with open(latest_file, "r", encoding="utf-8") as f:
    latest_data = json.load(f)

# Convert historical data into a dictionary for quick lookup
historical_dict = {hero["id"]: hero for hero in historical_data} if isinstance(historical_data, list) else {}

# Merge logic
def merge_heroes(old_heroes, new_heroes):
    """ Merge latest hero data with historical data while keeping track of changes. """

    for new_hero in new_heroes:
        hero_id = new_hero["id"]

        if hero_id in old_heroes:
            # Hero exists, update dynamically
            old_hero = old_heroes[hero_id]

            # Ensure name and role are always up to date
            old_hero["name"] = new_hero["name"]
            old_hero["role"] = new_hero["role"]

            # Merge transformations dynamically
            existing_trans_ids = {trans["id"] for trans in old_hero.get("transformations", [])}
            new_trans = [trans for trans in new_hero.get("transformations", []) if trans["id"] not in existing_trans_ids]
            old_hero.setdefault("transformations", []).extend(new_trans)

            # Merge abilities dynamically
            existing_ability_ids = {ability["id"] for ability in old_hero.get("abilities", [])}
            new_abilities = [ability for ability in new_hero.get("abilities", []) if ability["id"] not in existing_ability_ids]
            old_hero.setdefault("abilities", []).extend(new_abilities)

            # Merge costumes dynamically
            existing_costume_ids = {costume["id"] for costume in old_hero.get("costumes", [])}
            new_costumes = [costume for costume in new_hero.get("costumes", []) if costume["id"] not in existing_costume_ids]
            old_hero.setdefault("costumes", []).extend(new_costumes)

        else:
            # New hero, add them to the dataset
            old_heroes[hero_id] = new_hero

    return list(old_heroes.values())

# Merge latest hero data into the historical dataset
updated_heroes = merge_heroes(historical_dict, latest_data)

# Save updated data into the historical debug file
with open(output_file, "w", encoding="utf-8") as f:
    json.dump(updated_heroes, f, indent=4, ensure_ascii=False)

print(f"Historical hero data written to {output_file} for debugging.")
