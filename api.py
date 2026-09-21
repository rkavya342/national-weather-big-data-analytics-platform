from flask import Flask, jsonify
import sqlite3

app = Flask(__name__)

DATABASE = "weather_platform.db"


def get_database():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


@app.route("/api/alerts")
def get_alerts():

    connection = get_database()

    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            id,
            event_type,
            title,
            description,
            alert_date,
            link,
            source
        FROM alerts
        ORDER BY id DESC
    """)

    alerts = [dict(row) for row in cursor.fetchall()]

    connection.close()

    return jsonify(alerts)


@app.route("/")
def home():
    return "National Weather Platform API is running!"


if __name__ == "__main__":
    app.run(debug=True)