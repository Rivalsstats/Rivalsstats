import json
import os
from datetime import datetime

# File paths
historical_file = "data/ranks_historical.json"
latest_file = "data/latest_ranks.json"

# Load existing historical data
if os.path.exists(historical_file):
    with open(historical_file, "r", encoding="utf-8") as f:
        historical_data = json.load(f)
else:
    historical_data = {}

# Load latest rank data
with open(latest_file, "r", encoding="utf-8") as f:
    latest_data = json.load(f)

# Get current timestamp
timestamp = datetime.utcnow().isoformat()

# Merge logic
for rank, values in latest_data.items():
    if rank not in historical_data:
        historical_data[rank] = {}

    # Handle rank subdivisions (1, 2, 3, or total)
    for key, value in values.items():
        if key == "image":
            historical_data[rank]["image"] = value
            continue

        if key not in historical_data[rank]:
            historical_data[rank][key] = {"current": value, "historic": []}

        # Append only if the value has changed
        if historical_data[rank][key]["current"] != value:
            historical_data[rank][key]["historic"].append({
                "timestamp
