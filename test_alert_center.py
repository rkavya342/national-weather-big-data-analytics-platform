import unittest
from datetime import datetime
from app import app
from database.db import (
    get_db_connection,
    init_db,
    save_api_weather_data,
    fetch_national_alerts,
    fetch_alert_details,
    resolve_weather_alert
)

class TestAlertCenter(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Initialize database schema before running alert tests."""
        success, msg = init_db()
        assert success, f"Database init failed: {msg}"

    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def test_01_weather_alerts_table_exists(self):
        """Verify weather_alerts table exists in PostgreSQL database."""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'weather_alerts'
            );
        """)
        exists = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        self.assertTrue(exists, "weather_alerts table should exist in PostgreSQL database.")

    def test_02_alert_creation_and_deduplication(self):
        """Verify automatic alert creation upon severe weather ingestion and 6-hr deduplication."""
        test_obs = {
            "source": "OpenWeatherMap API Test",
            "city": "AlertTestCity",
            "state": "Maharashtra",
            "latitude": 19.0760,
            "longitude": 72.8777,
            "temperature": 29.5,
            "humidity": 95.0,
            "wind_speed": 45.0,
            "weather_condition": "Rain",
            "weather_description": "heavy intensity rain with severe flooding risk",
            "recorded_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "event_type": "Heavy Rainfall",
            "event_confidence": 88.50,
            "classified_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        # 1. Ingest first observation -> should generate new alert
        success, obs_id = save_api_weather_data(test_obs)
        self.assertTrue(success, f"Failed to save observation: {obs_id}")

        # Check alert was created
        success, alerts_data = fetch_national_alerts(city="AlertTestCity")
        self.assertTrue(success)
        alerts = alerts_data["alerts"]
        self.assertGreaterEqual(len(alerts), 1, "At least one alert should be created for AlertTestCity.")

        first_alert = alerts[0]
        self.assertEqual(first_alert["event_type"], "Heavy Rainfall")
        self.assertEqual(first_alert["severity"], "HIGH")
        self.assertEqual(first_alert["status"], "Active")

        # 2. Ingest second observation for same city & event -> deduplication should suppress second alert creation
        success2, obs_id2 = save_api_weather_data(test_obs)
        self.assertTrue(success2)

        success, alerts_data_2 = fetch_national_alerts(city="AlertTestCity")
        alerts_2 = alerts_data_2["alerts"]
        self.assertEqual(len(alerts_2), len(alerts), "Duplicate alert should be suppressed within 6-hour window.")

    def test_03_fetch_national_alerts_api(self):
        """Test GET /api/alerts endpoint with filters and analytics payload."""
        response = self.app.get('/api/alerts?severity=HIGH&status=Active')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["success"])
        self.assertIn("alerts", data["data"])
        self.assertIn("summary", data["data"])
        self.assertIn("analytics", data["data"])
        self.assertIn("timeline", data["data"])

    def test_04_alerts_ui_page(self):
        """Test GET /alerts UI route returns 200 OK HTML."""
        response = self.app.get('/alerts')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"NATIONAL WEATHER EVENT MONITORING & ALERT CENTER", response.data)

    def test_05_alert_details_and_resolution(self):
        """Test fetching alert details and resolving an alert."""
        success, alerts_data = fetch_national_alerts(city="AlertTestCity")
        self.assertTrue(success)
        alerts = alerts_data["alerts"]
        self.assertGreaterEqual(len(alerts), 1)

        alert_id = alerts[0]["id"]

        # Fetch details
        success, details = fetch_alert_details(alert_id)
        self.assertTrue(success)
        self.assertEqual(details["alert"]["id"], alert_id)

        # Resolve alert as admin (using db function)
        res_success, res_msg = resolve_weather_alert(alert_id, resolved_by="AdminTest")
        self.assertTrue(res_success, f"Failed to resolve alert: {res_msg}")

        # Verify status updated to Resolved
        success, details_after = fetch_alert_details(alert_id)
        self.assertTrue(success)
        self.assertEqual(details_after["alert"]["status"], "Resolved")
        self.assertIsNotNone(details_after["alert"]["resolved_at"])

if __name__ == '__main__':
    unittest.main()
