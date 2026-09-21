import json

# Read cleaned alerts
with open("cleaned_sachet_alerts.json", "r", encoding="utf-8") as file:
    alerts = json.load(file)

unique_alerts = []
seen = set()

for alert in alerts:

    # Use link as the unique identifier
    unique_id = alert.get("link", "").strip()

    # If link is empty, use title + date
    if not unique_id:
        unique_id = (
            alert.get("title", "").strip()
            + alert.get("date", "").strip()
        )

    if unique_id not in seen:
        seen.add(unique_id)
        unique_alerts.append(alert)

# Save deduplicated data
with open("unique_sachet_alerts.json", "w", encoding="utf-8") as file:
    json.dump(unique_alerts, file, indent=4, ensure_ascii=False)

print("Original alerts :", len(alerts))
print("Unique alerts   :", len(unique_alerts))
print("Duplicates removed:", len(alerts) - len(unique_alerts))
print("Saved to unique_sachet_alerts.json")