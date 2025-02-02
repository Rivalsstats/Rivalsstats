import json
import os
import requests

# File paths
historical_file = "data/codes_historical.json"
latest_file = "data/latest_codes.json"

# Load previous codes if they exist
if os.path.exists(historical_file):
    with open(historical_file, "r", encoding="utf-8") as f:
        historical_codes = json.load(f)
else:
    historical_codes = []

# Load latest API codes
with open(latest_file, "r", encoding="utf-8") as f:
    latest_codes = json.load(f)

# Extract existing code IDs for comparison
historical_code_ids = {entry["code"] for entry in historical_codes}
new_codes = [code for code in latest_codes if code["code"] not in historical_code_ids]

# Send notification if new codes are found
if new_codes:
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")

    message = "**New Marvel Rivals Codes Available!** 🎁\n"
    for code in new_codes:
        message += f"**Code:** `{code['code']}`\n"
        message += f"**Rewards:** {code['rewards']}\n"
        message += f"**Expires:** {code['expiringDate']}\n\n"

    payload = {"content": message}
    response = requests.post(webhook_url, json=payload)

    if response.status_code == 204:
        print("✅ Notification sent to Discord!")
    else:
        print(f"❌ Failed to send Discord notification: {response.status_code}, {response.text}")

# Merge the latest codes into the historical dataset
updated_codes = historical_codes + new_codes

# Save updated code history
with open(historical_file, "w", encoding="utf-8") as f:
    json.dump(updated_codes, f, indent=4, ensure_ascii=False)

print(f"Updated code history saved to {historical_file}.")
