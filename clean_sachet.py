import json
import re

# Read the collected SACHET data
with open("sachet_alerts.json", "r", encoding="utf-8") as file:
    alerts = json.load(file)

cleaned_alerts = []

for alert in alerts:

    title = alert.get("title", "").strip()
    description = alert.get("description", "").strip()
    date = alert.get("date", "").strip()
    link = alert.get("link", "").strip()

    # Try to identify common weather/disaster events
    text = (title + " " + description).lower()

    if "flood" in text:
        event_type = "Flood"
    elif "thunderstorm" in text:
        event_type = "Thunderstorm"
    elif "heavy rain" in text or "rainfall" in text:
        event_type = "Rainfall"
    elif "heat" in text:
        event_type = "Heatwave"
    elif "fog" in text:
        event_type = "Fog"
    elif "dust" in text:
        event_type = "Dust Storm"
    elif "wind" in text:
        event_type = "Strong Wind"
    elif "cyclone" in text:
        event_type = "Cyclone"
    else:
        event_type = "Other"

    cleaned_alert = {
        "event_type": event_type,
        "title": re.sub(r"\s+", " ", title),
        "date": date,
        "description": re.sub(r"\s+", " ", description),
        "link": link
    }

    cleaned_alerts.append(cleaned_alert)

# Save cleaned data
with open("cleaned_sachet_alerts.json", "w", encoding="utf-8") as file:
    json.dump(cleaned_alerts, file, indent=4, ensure_ascii=False)

print("Successfully cleaned", len(cleaned_alerts), "alerts.")
print("Saved to cleaned_sachet_alerts.json")