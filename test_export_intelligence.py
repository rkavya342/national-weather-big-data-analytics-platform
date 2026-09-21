import unittest
import csv
import json
import io
from app import app
from database.db import init_db

class TestExportIntelligence(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Ensure database schema is initialized."""
        success, msg = init_db()
        assert success, f"Database init failed: {msg}"

    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def test_01_exports_ui_page(self):
        """Test GET /exports renders HTML page successfully."""
        response = self.app.get('/exports')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"DATA EXPORT & INTELLIGENCE REPORTS", response.data)

    def test_02_export_summary_api(self):
        """Test GET /api/export/summary returns matching live statistics."""
        response = self.app.get('/api/export/summary?event_type=all&state=all')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["success"])
        self.assertIn("total_reports", data["data"])
        self.assertIn("date_range", data["data"])
        self.assertIn("events_count", data["data"])
        self.assertIn("states_count", data["data"])
        self.assertIn("average_trust", data["data"])

    def test_03_export_reports_csv(self):
        """Test GET /api/export/reports/csv returns downloadable CSV with header."""
        response = self.app.get('/api/export/reports/csv')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, 'text/csv')
        self.assertIn('attachment; filename=weather_reports_export.csv', response.headers.get('Content-Disposition', ''))

        content = response.data.decode('utf-8')
        reader = csv.reader(io.StringIO(content))
        header = next(reader)
        self.assertIn("id", header)
        self.assertIn("source", header)
        self.assertIn("report_text", header)
        self.assertIn("verification_result", header)
        self.assertIn("trust_score", header)

    def test_04_export_reports_json(self):
        """Test GET /api/export/reports/json returns downloadable JSON array."""
        response = self.app.get('/api/export/reports/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, 'application/json')
        self.assertIn('attachment; filename=weather_reports_export.json', response.headers.get('Content-Disposition', ''))

        data = json.loads(response.data.decode('utf-8'))
        self.assertIsInstance(data, list)

    def test_05_export_weather_csv(self):
        """Test GET /api/export/weather/csv returns weather observations CSV."""
        response = self.app.get('/api/export/weather/csv')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, 'text/csv')
        self.assertIn('attachment; filename=weather_observations_export.csv', response.headers.get('Content-Disposition', ''))

        content = response.data.decode('utf-8')
        reader = csv.reader(io.StringIO(content))
        header = next(reader)
        self.assertIn("city", header)
        self.assertIn("temperature", header)
        self.assertIn("weather_condition", header)

    def test_06_export_alerts_csv(self):
        """Test GET /api/export/alerts/csv returns weather alerts CSV."""
        response = self.app.get('/api/export/alerts/csv')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, 'text/csv')
        self.assertIn('attachment; filename=weather_alerts_export.csv', response.headers.get('Content-Disposition', ''))

        content = response.data.decode('utf-8')
        reader = csv.reader(io.StringIO(content))
        header = next(reader)
        self.assertIn("alert_id", header)
        self.assertIn("severity", header)
        self.assertIn("detected_at", header)

    def test_07_export_admin_audit_rbac(self):
        """Test admin audit log CSV export RBAC protection."""
        # Unauthenticated request -> expect 403
        resp_unauth = self.app.get('/api/export/admin-audit/csv')
        self.assertEqual(resp_unauth.status_code, 403)

        # Authenticated as admin -> expect 200 OK
        with self.app.session_transaction() as sess:
            sess["username"] = "admin"
            sess["role"] = "admin"

        resp_admin = self.app.get('/api/export/admin-audit/csv')
        self.assertEqual(resp_admin.status_code, 200)
        self.assertEqual(resp_admin.mimetype, 'text/csv')
        self.assertIn('attachment; filename=admin_audit_actions_export.csv', resp_admin.headers.get('Content-Disposition', ''))

    def test_08_intelligence_summary_api(self):
        """Test GET /api/intelligence-summary returns structured report data."""
        response = self.app.get('/api/intelligence-summary')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["success"])
        report = data["data"]
        self.assertIn("national_overview", report)
        self.assertIn("major_events", report)
        self.assertIn("verification_overview", report)
        self.assertIn("data_quality", report)
        self.assertIn("alert_status", report)
        self.assertIn("key_observations", report)

    def test_09_download_intelligence_summary(self):
        """Test GET /api/export/intelligence-summary/download returns text summary file."""
        response = self.app.get('/api/export/intelligence-summary/download')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, 'text/plain')
        self.assertIn('attachment; filename=national_weather_intelligence_summary.txt', response.headers.get('Content-Disposition', ''))
        self.assertIn(b"NATIONAL WEATHER INTELLIGENCE SUMMARY REPORT", response.data)

    def test_10_security_credentials_scrubbed(self):
        """Verify exports never contain passwords, secret keys, or database credentials."""
        csv_resp = self.app.get('/api/export/reports/csv')
        csv_text = csv_resp.data.decode('utf-8')
        self.assertNotIn("POSTGRES_PASSWORD", csv_text)
        self.assertNotIn("OPENWEATHER_API_KEY", csv_text)
        self.assertNotIn("SECRET_KEY", csv_text)
        self.assertNotIn("password_hash", csv_text)

if __name__ == '__main__':
    unittest.main()
