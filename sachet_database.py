import sqlite3
import json

# Connect to SQLite database
connection = sqlite3.connect("weather_platform.db")

cursor = connection.cursor()

# Create alerts table
cursor.execute("""
CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT,
    title TEXT,
    description TEXT,
    alert_date TEXT,
    link TEXT UNIQUE,
    source TEXT
)
""")

# Read deduplicated SACHET data
with open("unique_sachet_alerts.json", "r", encoding="utf-8") as file:
    alerts = json.load(file)

# Insert alerts
for alert in alerts:

    cursor.execute("""
    INSERT OR IGNORE INTO alerts
    (event_type, title, description, alert_date, link, source)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (
        alert.get("event_type", ""),
        alert.get("title", ""),
        alert.get("description", ""),
        alert.get("date", ""),
        alert.get("link", ""),
        "SACHET/NDMA"
    ))

# Save changes
connection.commit()

# Check number of records
cursor.execute("SELECT COUNT(*) FROM alerts")
count = cursor.fetchone()[0]

print("Database created successfully!")
print("Alerts stored:", count)

connection.close()