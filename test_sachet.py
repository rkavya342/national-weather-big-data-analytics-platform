import requests
import xml.etree.ElementTree as ET
import json

url = "https://sachet.ndma.gov.in/cap_public_website/rss/rss_india.xml"

response = requests.get(url, timeout=30)
response.raise_for_status()

root = ET.fromstring(response.content)

alerts = []

for item in root.findall(".//item"):

    alert = {
        "title": item.findtext("title", default=""),
        "link": item.findtext("link", default=""),
        "date": item.findtext("pubDate", default=""),
        "description": item.findtext("description", default="")
    }

    alerts.append(alert)

# Save alerts into a JSON file
with open("sachet_alerts.json", "w", encoding="utf-8") as file:
    json.dump(alerts, file, indent=4, ensure_ascii=False)

print("Successfully collected", len(alerts), "alerts.")
print("Saved to sachet_alerts.json")