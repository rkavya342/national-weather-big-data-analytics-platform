import sqlite3

connection = sqlite3.connect("weather_platform.db")
cursor = connection.cursor()

cursor.execute("""
SELECT id, event_type, title, alert_date, source
FROM alerts
LIMIT 10
""")

rows = cursor.fetchall()

print("\n===== STORED SACHET ALERTS =====\n")

for row in rows:
    print("ID         :", row[0])
    print("Event      :", row[1])
    print("Title      :", row[2])
    print("Date       :", row[3])
    print("Source     :", row[4])
    print("-" * 70)

connection.close()