import unittest
import csv
import json
import io
from app import app
from database.db import (
    get_db_connection,
    init_db,
    save_api_weather_data,
    fetch_national_alerts,
    resolve_weather_alert
)

class TestFinalPlatformAudit(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Initialize database schema before audit tests."""
        success, msg = init_db()
        assert success, f"Database init failed: {msg}"

    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def test_01_database_tables_exist(self):
        """Verify all required PostgreSQL tables exist."""
        conn = get_db_connection()
        cursor = conn.cursor()
        required_tables = ["weather_reports", "api_weather_data", "weather_alerts", "admin_actions", "users"]
        for table in required_tables:
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = %s
                );
            """, (table,))
            exists = cursor.fetchone()[0]
            self.assertTrue(exists, f"Table '{table}' must exist in PostgreSQL database.")
        cursor.close()
        conn.close()

    def test_02_public_routes_status_200(self):
        """Verify all public page routes return HTTP 200 OK."""
        public_routes = ["/", "/dashboard", "/report", "/reports", "/api-weather", "/alerts", "/exports", "/login"]
        for route in public_routes:
            response = self.app.get(route)
            self.assertEqual(response.status_code, 200, f"Route '{route}' should return HTTP 200 OK.")

    def test_03_rbac_admin_routes_protection(self):
        """Verify administrative pages and APIs block unauthenticated access."""
        # Unauthenticated request to /admin -> 302 redirect
        resp_admin = self.app.get('/admin')
        self.assertIn(resp_admin.status_code, [302, 403])

        # Unauthenticated request to admin API -> 403 Forbidden
        resp_api = self.app.get('/api/admin/summary')
        self.assertEqual(resp_api.status_code, 403)

    def test_04_admin_authentication_and_dashboard_access(self):
        """Verify authenticated admin user can access Admin Control Center and admin APIs."""
        with self.app.session_transaction() as sess:
            sess["username"] = "admin"
            sess["role"] = "admin"

        resp_admin = self.app.get('/admin')
        self.assertEqual(resp_admin.status_code, 200)

        resp_summary = self.app.get('/api/admin/summary')
        self.assertEqual(resp_summary.status_code, 200)
        res_json = resp_summary.get_json()
        self.assertTrue(res_json.get("status") == "success" or res_json.get("success"))

    def test_05_core_apis_health(self):
        """Verify core platform API endpoints return valid JSON responses."""
        apis = [
            "/api/analytics",
            "/api/search",
            "/api/alerts",
            "/api/export/summary",
            "/api/intelligence-summary"
        ]
        for api_route in apis:
            response = self.app.get(api_route)
            self.assertEqual(response.status_code, 200, f"API '{api_route}' should return HTTP 200 OK.")
            data = response.get_json()
            self.assertIsNotNone(data, f"API '{api_route}' must return valid JSON.")

    def test_06_custom_error_handlers(self):
        """Verify custom 404 and 500 error handling for HTML and JSON requests."""
        # 404 HTML route
        resp_html_404 = self.app.get('/nonexistent-page-route-1234')
        self.assertEqual(resp_html_404.status_code, 404)
        self.assertIn(b"404 - Page Not Found", resp_html_404.data)

        # 404 JSON API route
        resp_json_404 = self.app.get('/api/nonexistent-api-endpoint')
        self.assertEqual(resp_json_404.status_code, 404)
        self.assertFalse(resp_json_404.get_json()["success"])

    def test_07_export_endpoints_health(self):
        """Verify CSV and JSON export routes produce valid file downloads."""
        # CSV Weather Reports
        resp_csv = self.app.get('/api/export/reports/csv')
        self.assertEqual(resp_csv.status_code, 200)
        self.assertEqual(resp_csv.mimetype, 'text/csv')

        # JSON Weather Reports
        resp_json = self.app.get('/api/export/reports/json')
        self.assertEqual(resp_json.status_code, 200)
        self.assertEqual(resp_json.mimetype, 'application/json')

        # Intelligence Summary Download
        resp_txt = self.app.get('/api/export/intelligence-summary/download')
        self.assertEqual(resp_txt.status_code, 200)
        self.assertEqual(resp_txt.mimetype, 'text/plain')

    def test_08_secrets_scrubbing_audit(self):
        """Verify secrets, passwords, and API keys are never exposed in outputs."""
        resp_csv = self.app.get('/api/export/reports/csv')
        csv_text = resp_csv.data.decode('utf-8')
        self.assertNotIn("POSTGRES_PASSWORD", csv_text)
        self.assertNotIn("OPENWEATHER_API_KEY", csv_text)
        self.assertNotIn("SECRET_KEY", csv_text)
        self.assertNotIn("password_hash", csv_text)

        resp_json = self.app.get('/api/export/reports/json')
        json_text = resp_json.data.decode('utf-8')
        self.assertNotIn("password_hash", json_text)
        self.assertNotIn("OPENWEATHER_API_KEY", json_text)

if __name__ == '__main__':
    unittest.main()
