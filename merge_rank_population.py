import csv
import json
import os
from datetime import datetime

# File paths
historical_file = "data/historical/ranks_historical.csv"
latest_file = "data/latest/latest_ranks.json"

# Load latest rank data
with open(latest_file, "r", encoding="utf-8") as f:
    latest_data = json.load(f)

# Get current timestamp
timestamp = datetime.utcnow().isoformat()

# Check if historical CSV exists (to determine if headers are needed)
file_exists = os.path.isfile(historical_file)

# Open CSV file in append mode
with open(historical_file, "a", encoding="utf-8", newline="") as f:
    writer = csv.writer(f)

    # Write headers only if the file is new
    if not file_exists:
        writer.writerow(["timestamp", "rank", "division", "population_count"])

    # Convert JSON structure to CSV rows
    for rank, values in latest_data.items():
        for key, value in values.items():
            if key == "image":
                continue  # Skip images

            # Write a new row for each rank/division entry
            writer.writerow([timestamp, rank, key, value])

print(f"✅ Updated rank population history (saved to {historical_file}).")
