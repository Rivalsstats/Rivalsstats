import json
import os
import requests
from datetime import datetime

# File paths
historical_file = "data/historical/codes_historical.json"
latest_file = "data/latest/latest_codes.json"

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
    webhook_urls = os.getenv("DISCORD_WEBHOOK_URLS", "").split(",")
    
    message = "**New Marvel Rivals Codes Available!** 🎁\n"
    embeds = []
    for code in new_codes:
        expiring_date = code["expiringDate"]
        expiring_timestamp = int(datetime.strptime(expiring_date, "%B %d, %Y %H:%M UTC").timestamp())
       embed = {
            "title": "New Marvel Rivals Code Available! 🎁",
            "color": 0xffc887,  # Green color 
            "thumbnail": {
                "url": "https://rivalsstats.com/favicon/web-app-manifest-512x512.png"
            },
            "fields": [
                {"name": "Code", "value": f"```\n{code['code']}\n```", "inline": False},
                {"name": "Rewards", "value": code["rewards"], "inline": False},
                {"name": "Expires", "value": f"<t:{expiring_timestamp}:R>", "inline": False},
                # Extra field for clickable link
                {"name": "RivalsStats", "value": "[Visit RivalsStats](https://rivalsstats.com)", "inline": False}
            ],
            "footer": {
                "text": "Made by Jods"
            }
        }
        embeds.append(embed)
    payload = {"embeds": embeds} #"content": message
    for url in webhook_urls:
        response = requests.post(url, json=payload)

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
