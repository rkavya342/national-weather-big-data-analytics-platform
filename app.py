import csv
import io
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, jsonify, request, redirect, url_for, flash, session, Response, make_response
from dotenv import load_dotenv, find_dotenv

from database.db import (
    test_db_connection,
    init_db,
    fetch_all_reports,
    insert_citizen_report,
    save_api_weather_data,
    fetch_recent_api_weather_data,
    fetch_total_api_weather_count,
    fetch_ai_event_summary,
    fetch_classified_events,
    classify_existing_unclassified_data,
    analyze_unanalyzed_weather_reports,
    analyze_and_update_report,
    fetch_report_verification_summary,
    fetch_duplicate_summary,
    fetch_source_trust_summary,
    fetch_multi_source_summary,
    fetch_map_geographic_records,
    fetch_advanced_analytics,
    search_weather_reports,
    fetch_report_by_id,
    authenticate_user,
    fetch_admin_summary,
    fetch_admin_report_details,
    update_report_verification,
    fetch_admin_action_history,
    fetch_national_alerts,
    fetch_alert_details,
    resolve_weather_alert,
    fetch_export_summary_metrics,
    fetch_filtered_reports_for_export,
    fetch_filtered_observations_for_export,
    fetch_filtered_alerts_for_export,
    fetch_admin_audit_for_export,
    generate_weather_intelligence_summary
)
from services.weather_api import fetch_city_weather, fetch_weather_by_coords
from services.ingestion_service import run_weather_ingestion, get_latest_ingestion_status
from services.scheduler import init_scheduler
from services.multi_source_ingestion import import_sample_reports
from services.sachet_ingestion import fetch_and_store_sachet_alerts
from services.mastodon_ingestion import ingest_mastodon_reports, get_mastodon_ingestion_status
from socketio_instance import socketio, broadcast_new_report, broadcast_weather_update

# Load environment variables from .env with explicit path resolution and override
env_file = find_dotenv()
if env_file:
    load_dotenv(env_file, override=True)
else:
    load_dotenv(override=True)

app = Flask(__name__)
app.secret_key = "national-weather-intelligence-dev-secret-key"

# Initialize Flask-SocketIO with application context
socketio.init_app(app)

# Initialize database schema on startup if DB is connected
try:
    init_db()
    classify_existing_unclassified_data()
    analyze_unanalyzed_weather_reports()
    fetch_and_store_sachet_alerts()
except Exception:
    pass

# Initialize background periodic weather ingestion scheduler (15-minute interval)
init_scheduler(app)


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        role = session.get("role")
        if not role or role not in ["admin", "analyst"]:
            if request.path.startswith("/api/"):
                return jsonify({"status": "error", "message": "Unauthorized access. Admin or Analyst role required."}), 403
            flash("Unauthorized access. Admin Control Center requires Admin or Analyst login.", "danger")
            return redirect(url_for("login", next=request.path))
        return f(*args, **kwargs)
    return decorated_function


@app.route("/login", methods=["GET", "POST"])
def login():
    """
    Login page and user authentication handler.
    """
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        next_page = request.form.get("next", "")

        success, user_or_err = authenticate_user(username, password)
        if success:
            session["user_id"] = user_or_err["id"]
            session["username"] = user_or_err["username"]
            session["role"] = user_or_err["role"]
            flash(f"Welcome back, {user_or_err['username']}! Logged in as {user_or_err['role'].upper()}.", "success")

            if next_page and next_page.startswith("/"):
                return redirect(next_page)
            return redirect(url_for("admin_dashboard") if user_or_err["role"] in ["admin", "analyst"] else url_for("dashboard"))
        else:
            flash(f"Login failed: {user_or_err}", "danger")

    return render_template("login.html")


@app.route("/logout")
def logout():
    """
    Log out active user session.
    """
    session.clear()
    flash("You have been logged out successfully.", "info")
    return redirect(url_for("dashboard"))


# ==========================================
# ADMIN & VERIFICATION CONTROL CENTER ROUTES
# ==========================================

@app.route("/admin")
@admin_required
def admin_dashboard():
    """
    Render Admin / Weather Report Verification Control Center dashboard.
    """
    return render_template("admin_dashboard.html")


@app.route("/admin/history")
@admin_required
def admin_history_page():
    """
    Render Admin Activity Audit History page.
    """
    return render_template("admin_history.html")


@app.route("/api/admin/summary")
@admin_required
def api_admin_summary():
    """
    API returning summary metric cards for Admin Control Center.
    """
    success, summary = fetch_admin_summary()
    if success:
        return jsonify({"status": "success", "summary": summary}), 200
    return jsonify({"status": "error", "message": summary}), 500


@app.route("/api/admin/reports")
@admin_required
def api_admin_reports():
    """
    API returning filtered, paginated report list for Admin Control Center table with attention levels.
    """
    keyword = request.args.get("keyword", "").strip()
    event_type = request.args.get("event_type", "All").strip()
    state = request.args.get("state", "All").strip()
    city = request.args.get("city", "").strip()
    source = request.args.get("source", "All").strip()
    verification = request.args.get("verification", "All").strip()
    trust_level = request.args.get("trust_level", "All").strip()
    duplicate_status = request.args.get("duplicate_status", "All").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    sort_by = request.args.get("sort_by", "date_desc").strip()
    page = request.args.get("page", 1)
    per_page = request.args.get("per_page", 20)

    success, result = search_weather_reports(
        keyword=keyword,
        event_type=event_type,
        state=state,
        city=city,
        source=source,
        verification=verification,
        trust_level=trust_level,
        duplicate_status=duplicate_status,
        date_from=date_from,
        date_to=date_to,
        sort_by=sort_by,
        page=page,
        per_page=per_page
    )

    if success:
        return jsonify({"status": "success", "data": result}), 200
    return jsonify({"status": "error", "message": result}), 500


@app.route("/api/admin/report/<int:report_id>")
@admin_required
def api_admin_report_details(report_id):
    """
    API returning complete report metadata, latest weather evidence, duplicate links, and action history.
    """
    success, data = fetch_admin_report_details(report_id)
    if success:
        return jsonify({"status": "success", "data": data}), 200
    status_code = 404 if "not found" in str(data).lower() else 500
    return jsonify({"status": "error", "message": data}), status_code


@app.route("/api/admin/report/<int:report_id>/verify", methods=["POST"])
@admin_required
def api_admin_verify_report(report_id):
    """
    API allowing administrator to change report verification result, edit verification reason, 
    recalculate trust score, and record audit log entry in admin_actions.
    """
    payload = request.get_json(silent=True) or request.form
    new_verification = (payload.get("new_verification") or payload.get("verification_result") or "").strip()
    reason = (payload.get("reason") or payload.get("verification_reason") or "").strip()
    action_type = (payload.get("action_type") or "Updated Verification").strip()

    if not new_verification or new_verification not in ["Verified", "Likely Consistent", "Needs Verification", "Suspicious", "Unverified"]:
        return jsonify({"status": "error", "message": "Invalid verification result selected."}), 400

    performed_by = session.get("username", "Admin")
    success, result = update_report_verification(
        report_id=report_id,
        new_verification=new_verification,
        reason=reason,
        action_type=action_type,
        performed_by=performed_by
    )

    if success:
        broadcast_weather_update(result)
        return jsonify({"status": "success", "message": "Report verification updated successfully.", "data": result}), 200
    return jsonify({"status": "error", "message": result}), 500


@app.route("/api/admin/history")
@admin_required
def api_admin_history():
    """
    API returning paginated admin action audit logs from admin_actions table.
    """
    page = request.args.get("page", 1)
    per_page = request.args.get("per_page", 20)
    success, result = fetch_admin_action_history(page=page, per_page=per_page)
    if success:
        return jsonify({"status": "success", "data": result}), 200
    return jsonify({"status": "error", "message": result}), 500



@app.route("/")
@app.route("/dashboard")
def dashboard():
    """
    Render the main National Weather Intelligence Dashboard.
    Includes AI Weather Event Classification summary metrics, Citizen Verification status counters,
    Duplicate Report counters, Source Trust summary stats, Multi-Source ingestion stats, and recent classified events table.
    """
    event_filter = request.args.get("event_filter", "All").strip()

    # Fetch AI event classification summary stats
    _, ai_summary = fetch_ai_event_summary()

    # Fetch citizen report verification summary counters
    _, verification_summary = fetch_report_verification_summary()

    # Fetch duplicate & related report summary counters
    _, duplicate_summary = fetch_duplicate_summary()

    # Fetch Source Trust summary & breakdown rows
    _, trust_summary = fetch_source_trust_summary()

    # Fetch Multi-Source summary counters & chart data
    _, multi_source_summary = fetch_multi_source_summary()

    # Fetch classified event records with optional filtering
    _, classified_events = fetch_classified_events(event_filter=event_filter, limit=50)
    if not isinstance(classified_events, list):
        classified_events = []

    return render_template(
        "dashboard.html",
        ai_summary=ai_summary,
        verification_summary=verification_summary,
        duplicate_summary=duplicate_summary,
        trust_summary=trust_summary,
        multi_source_summary=multi_source_summary,
        classified_events=classified_events,
        selected_event_filter=event_filter
    )


@app.route("/map")
def live_map_page():
    """
    Render dedicated Live Weather Event Map page.
    """
    return render_template("live_map.html")



@app.route("/import-sample-reports", methods=["GET", "POST"])
def import_sample_reports_route():
    """
    Import multi-source weather sample reports into PostgreSQL database.
    Executes automated event classification, verification, duplicate detection, and source trust scoring.
    Prevents duplicate imports if sample records already exist.
    """
    try:
        imported, skipped, analyzed, total = import_sample_reports()
        flash(
            f"Multi-source sample report ingestion complete! {imported} new reports imported, {skipped} skipped as existing duplicates, and {analyzed} reports fully analyzed across classification, verification, and trust scoring.",
            "success" if imported > 0 or skipped > 0 else "info"
        )
    except Exception as e:
        flash(f"Error during multi-source sample report ingestion: {str(e)}", "danger")

    return redirect(url_for("dashboard"))


@app.route("/api/map-data")
def api_map_data():
    """
    Backend JSON API endpoint returning valid geographic weather records (latitude, longitude)
    for rendering on the interactive Leaflet India weather map.
    """
    success, data_or_error = fetch_map_geographic_records()
    if success:
        return jsonify({
            "status": "success",
            "count": len(data_or_error),
            "records": data_or_error
        }), 200
    else:
        return jsonify({
            "status": "error",
            "message": "Failed to fetch geographic map records.",
            "error_detail": data_or_error
        }), 500


@app.route("/api/dashboard-summary")
def api_dashboard_summary():
    """
    Backend JSON API endpoint returning all current dashboard summary metrics
    for asynchronous real-time UI component updates.
    """
    _, ai_summary = fetch_ai_event_summary()
    _, verification_summary = fetch_report_verification_summary()
    _, duplicate_summary = fetch_duplicate_summary()
    _, trust_summary = fetch_source_trust_summary()
    _, multi_source_summary = fetch_multi_source_summary()
    _, classified_events = fetch_classified_events(limit=10)

    return jsonify({
        "status": "success",
        "ai_summary": ai_summary,
        "verification_summary": verification_summary,
        "duplicate_summary": duplicate_summary,
        "trust_summary": trust_summary,
        "multi_source_summary": multi_source_summary,
        "classified_events": classified_events if isinstance(classified_events, list) else []
    }), 200


@app.route("/api/analytics")
def api_analytics():
    """
    Backend JSON API endpoint returning comprehensive aggregated weather analytics
    from PostgreSQL with support for filtering by date_from, date_to, event_type, state, and source.
    """
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    event_type = request.args.get("event_type", "").strip()
    state = request.args.get("state", "").strip()
    source = request.args.get("source", "").strip()

    success, data_or_error = fetch_advanced_analytics(
        start_date=date_from,
        end_date=date_to,
        event_type=event_type,
        state=state,
        source=source
    )

    if success:
        return jsonify({
            "status": "success",
            "filters": {
                "date_from": date_from,
                "date_to": date_to,
                "event_type": event_type,
                "state": state,
                "source": source
            },
            "analytics": data_or_error,
            "data": data_or_error
        }), 200
    else:
        return jsonify({
            "status": "error",
            "message": "Failed to fetch aggregated weather analytics.",
            "error_detail": data_or_error
        }), 500


@app.route("/db-test")
def db_test():
    """
    Test endpoint for PostgreSQL database connection.
    Executes SELECT version() and returns connection status.
    """
    success, detail = test_db_connection()
    if success:
        return jsonify({
            "status": "success",
            "message": "PostgreSQL database connection successful!",
            "postgres_version": detail
        }), 200
    else:
        return jsonify({
            "status": "error",
            "message": "Failed to connect to PostgreSQL database.",
            "error_detail": detail
        }), 500


@app.route("/init-db")
def initialize_database():
    """
    Endpoint to explicitly create/verify database tables.
    """
    success, message = init_db()
    if success:
        return jsonify({"status": "success", "message": message}), 200
    else:
        return jsonify({"status": "error", "message": message}), 500


@app.route("/api/search")
@app.route("/api/reports/search")
def api_search_reports():
    """
    Asynchronous JSON API for advanced report searching, multi-filter aggregation, sorting, and pagination.
    """
    keyword = request.args.get("keyword", "").strip()
    event_type = request.args.get("event_type", "All").strip()
    state = request.args.get("state", "All").strip()
    city = request.args.get("city", "").strip()
    source = request.args.get("source", "All").strip()
    verification = request.args.get("verification", "All").strip()
    trust_level = request.args.get("trust_level", "All").strip()
    duplicate_status = request.args.get("duplicate_status", "All").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    sort_by = request.args.get("sort_by", "date_desc").strip()
    page = request.args.get("page", 1)
    per_page = request.args.get("per_page", 20)

    # Date range validation
    if date_from and date_to and date_from > date_to:
        return jsonify({
            "status": "error",
            "message": "Invalid date range: 'Date From' cannot be later than 'Date To'."
        }), 400

    success, result = search_weather_reports(
        keyword=keyword,
        event_type=event_type,
        state=state,
        city=city,
        source=source,
        verification=verification,
        trust_level=trust_level,
        duplicate_status=duplicate_status,
        date_from=date_from,
        date_to=date_to,
        sort_by=sort_by,
        page=page,
        per_page=per_page
    )

    if success:
        return jsonify({
            "status": "success",
            "data": result
        }), 200
    else:
        return jsonify({
            "status": "error",
            "message": f"Database search failed: {result}"
        }), 500


@app.route("/api/reports/<int:report_id>")
def api_get_report_details(report_id):
    """
    Fetch full detail JSON payload for a single weather report modal view.
    """
    success, report_or_error = fetch_report_by_id(report_id)
    if success:
        return jsonify({
            "status": "success",
            "report": report_or_error
        }), 200
    else:
        status_code = 404 if "not found" in str(report_or_error).lower() else 500
        return jsonify({
            "status": "error",
            "message": report_or_error
        }), status_code


@app.route("/reports")
def view_reports():
    """
    Render weather reports table fetched from PostgreSQL database.
    Supports filtering by verification status, duplicate status, trust level, and source category.
    """
    status_filter = request.args.get("status_filter", "All").strip()
    duplicate_filter = request.args.get("duplicate_filter", "All").strip()
    trust_filter = request.args.get("trust_filter", "All").strip()
    source_filter = request.args.get("source_filter", "All").strip()

    success, data_or_error = fetch_all_reports(
        status_filter=status_filter,
        duplicate_filter=duplicate_filter,
        trust_filter=trust_filter,
        source_filter=source_filter
    )

    if success:
        return render_template(
            "reports.html",
            reports=data_or_error,
            db_error=None,
            selected_status_filter=status_filter,
            selected_duplicate_filter=duplicate_filter,
            selected_trust_filter=trust_filter,
            selected_source_filter=source_filter
        )
    else:
        return render_template(
            "reports.html",
            reports=[],
            db_error=data_or_error,
            selected_status_filter=status_filter,
            selected_duplicate_filter=duplicate_filter,
            selected_trust_filter=trust_filter,
            selected_source_filter=source_filter
        )


@app.route("/report", methods=["GET", "POST"])
def submit_report():
    """
    Handle Citizen Weather Report submission.
    GET: Render submit report form.
    POST: Validate input, insert report into PostgreSQL, run AI verification, duplicate detection & trust scoring.
    """
    if request.method == "POST":
        report_text = request.form.get("report_text", "").strip()
        event_type = request.form.get("event_type", "").strip()
        city = request.form.get("city", "").strip()
        state = request.form.get("state", "").strip()
        latitude = request.form.get("latitude", "").strip()
        longitude = request.form.get("longitude", "").strip()
        report_datetime = request.form.get("report_datetime", "").strip()
        image_url = request.form.get("image_url", "").strip()
        video_url = request.form.get("video_url", "").strip()

        # Input validation
        if not report_text or not event_type or not city or not state:
            flash("Please fill in all required fields (Description, Event Type, City, State).", "danger")
            default_dt = datetime.now().strftime("%Y-%m-%dT%H:%M")
            return render_template("submit_report.html", form_data=request.form, default_datetime=default_dt)

        # Database Insertion, Verification, Duplicate Detection & Trust Scoring
        success, result = insert_citizen_report(
            report_text=report_text,
            event_type=event_type,
            city=city,
            state=state,
            latitude=latitude,
            longitude=longitude,
            report_datetime=report_datetime,
            image_url=image_url,
            video_url=video_url
        )

        if success:
            try:
                broadcast_new_report({"report_id": result, "city": city, "event_type": event_type})
            except Exception:
                pass
            flash("Weather report submitted successfully and is awaiting verification.", "success")
            return redirect(url_for("view_reports"))
        else:
            flash(f"Error saving report to database: {result}", "danger")
            default_dt = datetime.now().strftime("%Y-%m-%dT%H:%M")
            return render_template("submit_report.html", form_data=request.form, default_datetime=default_dt)

    # GET request
    default_dt = datetime.now().strftime("%Y-%m-%dT%H:%M")
    return render_template("submit_report.html", form_data=None, default_datetime=default_dt)


@app.route("/analyze-report/<int:report_id>")
def analyze_report(report_id):
    """
    Manually trigger AI verification, duplicate re-analysis, and trust re-scoring for a report by ID.
    """
    success, res = analyze_and_update_report(report_id)
    if success:
        flash(
            f"AI Analysis completed for Report #{report_id}: {res['verification_result']} | Trust: {res['trust_score']}% ({res['trust_level']})",
            "info"
        )
    else:
        flash(f"Error analyzing report #{report_id}: {res}", "danger")
    return redirect(url_for("view_reports"))


@app.route("/api-weather")
def api_weather():
    """
    Live Weather Ingestion route via OpenWeatherMap API.
    GET: Optional query parameter 'city'. Fetches current weather data and stores in PostgreSQL.
    Displays background scheduler status and ingestion metrics.
    """
    city = request.args.get("city", "").strip()
    ingestion_status = get_latest_ingestion_status()
    mastodon_status = get_mastodon_ingestion_status()

    # Retrieve total API weather records count & recent records from database
    _, total_api_count = fetch_total_api_weather_count()
    _, recent_records = fetch_recent_api_weather_data(limit=25)
    if not isinstance(recent_records, list):
        recent_records = []

    if not city:
        return render_template(
            "api_weather.html",
            weather_data=None,
            error_msg=None,
            recent_records=recent_records,
            total_api_count=total_api_count,
            queried_city="",
            saved_status=False,
            ingestion_status=ingestion_status,
            mastodon_status=mastodon_status
        )

    # Call OpenWeatherMap service
    success, result = fetch_city_weather(city)

    if success:
        # Save to database (triggers automated event classification)
        saved, _ = save_api_weather_data(result)

        # Refresh recent records table & total count
        _, total_api_count = fetch_total_api_weather_count()
        _, updated_records = fetch_recent_api_weather_data(limit=25)
        if isinstance(updated_records, list):
            recent_records = updated_records

        return render_template(
            "api_weather.html",
            weather_data=result,
            error_msg=None,
            recent_records=recent_records,
            total_api_count=total_api_count,
            queried_city=city,
            saved_status=saved,
            ingestion_status=ingestion_status,
            mastodon_status=mastodon_status
        )
    else:
        return render_template(
            "api_weather.html",
            weather_data=None,
            error_msg=result,
            recent_records=recent_records,
            total_api_count=total_api_count,
            queried_city=city,
            saved_status=False,
            ingestion_status=ingestion_status,
            mastodon_status=mastodon_status
        )


@app.route("/api/weather/coords", methods=["GET"])
def api_weather_coords():
    """
    Fetch current weather data for specific latitude and longitude coordinates.
    Used by Leaflet map click weather lookup.
    """
    lat = request.args.get("lat")
    lon = request.args.get("lon")

    if not lat or not lon:
        return jsonify({"success": False, "error": "Latitude and longitude parameters are required."}), 400

    try:
        lat_val = float(lat)
        lon_val = float(lon)
    except ValueError:
        return jsonify({"success": False, "error": "Invalid latitude or longitude format."}), 400

    success, result = fetch_weather_by_coords(lat_val, lon_val)
    if success:
        saved, obs_id = save_api_weather_data(result)
        result["id"] = obs_id if saved else None
        return jsonify({"success": True, "data": result})
    else:
        return jsonify({"success": False, "error": result}), 400



@app.route("/ingest-weather", methods=["GET", "POST"])
def ingest_weather_route():
    """
    Trigger one complete weather data ingestion cycle for all configured major Indian cities.
    Returns JSON response if requested via API/AJAX/format=json, or redirects to UI with flash message.
    """
    summary = run_weather_ingestion()

    # Check if JSON format explicitly requested or AJAX
    if (
        request.is_json
        or request.headers.get("X-Requested-With") == "XMLHttpRequest"
        or request.args.get("format") == "json"
    ):
        return jsonify(summary), 200

    # If triggered from HTML UI button
    if summary.get("in_progress"):
        flash("Weather data ingestion is already in progress in the background. Please refresh in a moment.", "info")
    elif summary.get("success_count", 0) > 0:
        flash(
            f"Weather ingestion complete! Processed {summary['total_cities']} cities ({summary['success_count']} ingested & AI classified, {summary['failed_count']} failed).",
            "success"
        )
    else:
        flash(
            f"Weather ingestion completed with warnings: {summary.get('failed_count', 0)} cities failed. Check OpenWeather API key activation or network status.",
            "warning"
        )

    return redirect(url_for("api_weather"))


@app.route("/ingest-sachet", methods=["GET", "POST"])
@app.route("/api/ingest-sachet", methods=["GET", "POST"])
def ingest_sachet_route():
    """
    Trigger official SACHET/NDMA RSS disaster alert ingestion cycle.
    Returns JSON response if requested via API/AJAX/format=json, or redirects to Alerts page with flash message.
    """
    try:
        imported, skipped, total = fetch_and_store_sachet_alerts()
        result = {
            "status": "success",
            "imported": imported,
            "skipped": skipped,
            "total_fetched": total,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        if (
            request.is_json
            or request.headers.get("X-Requested-With") == "XMLHttpRequest"
            or request.args.get("format") == "json"
            or request.path.startswith("/api/")
        ):
            return jsonify(result), 200

        flash(f"SACHET / NDMA RSS Ingestion Complete: {imported} new alerts imported, {skipped} skipped as duplicates.", "success")
        return redirect(url_for("alerts_page"))
    except Exception as e:
        if (
            request.is_json
            or request.headers.get("X-Requested-With") == "XMLHttpRequest"
            or request.args.get("format") == "json"
            or request.path.startswith("/api/")
        ):
            return jsonify({"status": "error", "message": str(e)}), 500

        flash(f"SACHET RSS Ingestion Error: {str(e)}", "danger")
        return redirect(url_for("alerts_page"))


@app.route("/ingest-mastodon", methods=["GET", "POST"])
def ingest_mastodon_route():
    """
    Trigger public Mastodon hashtag weather ingestion cycle (#IMD, #WeatherUpdate, #RainAlert, #Monsoon).
    Returns JSON response if requested via API/AJAX/format=json, or redirects to UI with flash message.
    """
    try:
        status = ingest_mastodon_reports()

        # Check if JSON format explicitly requested or AJAX
        if (
            request.is_json
            or request.headers.get("X-Requested-With") == "XMLHttpRequest"
            or request.args.get("format") == "json"
        ):
            return jsonify(status), 200

        # If triggered from HTML UI button
        flash(
            f"Mastodon public feed ingestion complete! Received {status['received']} posts across tags (#IMD, #WeatherUpdate, #RainAlert, #Monsoon), inserted {status['inserted']} new weather reports, skipped {status['duplicates']} duplicates.",
            "success" if status['inserted'] > 0 or status['received'] > 0 else "info"
        )
    except Exception as e:
        if (
            request.is_json
            or request.headers.get("X-Requested-With") == "XMLHttpRequest"
            or request.args.get("format") == "json"
        ):
            return jsonify({"status": "error", "message": str(e)}), 500

        flash(f"Error during Mastodon ingestion: {str(e)}", "danger")

    return redirect(url_for("api_weather"))



@app.route("/alerts")
def alerts_page():
    """
    Render National Weather Event Monitoring & Alert Center page.
    """
    return render_template("alerts.html")


@app.route("/api/alerts")
def api_alerts():
    """
    Fetch filtered weather alerts, global summary metrics, analytics breakdowns, and timeline.
    """
    event_type = request.args.get("event_type", "all")
    severity = request.args.get("severity", "all")
    status = request.args.get("status", "all")
    state = request.args.get("state", "all")
    city = request.args.get("city", "")
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)

    success, data = fetch_national_alerts(
        event_type=event_type,
        severity=severity,
        status=status,
        state=state,
        city=city,
        page=page,
        per_page=per_page
    )

    if success:
        return jsonify({
            "success": True,
            "data": data
        }), 200
    else:
        return jsonify({
            "success": False,
            "error": data
        }), 500


@app.route("/api/alerts/<int:alert_id>")
def api_alert_details(alert_id):
    """
    Fetch details of a single weather alert including observation metrics and related citizen reports.
    """
    success, data = fetch_alert_details(alert_id)
    if success:
        return jsonify({
            "success": True,
            "data": data
        }), 200
    else:
        return jsonify({
            "success": False,
            "error": data
        }), 404


@app.route("/api/alerts/<int:alert_id>/resolve", methods=["POST"])
@admin_required
def api_resolve_alert(alert_id):
    """
    Mark an active weather alert as 'Resolved' (Admin only).
    """
    resolved_by = session.get("username", "Admin")
    success, message = resolve_weather_alert(alert_id, resolved_by=resolved_by)
    if success:
        broadcast_weather_update({"status": "alert_resolved", "alert_id": alert_id})
        return jsonify({
            "success": True,
            "message": message
        }), 200
    else:
        return jsonify({
            "success": False,
            "error": message
        }), 400


@app.route("/analyst")
def analyst_page():
    """
    Render Weather Intelligence Analyst Workbench page.
    """
    return render_template("analyst.html")


@app.route("/exports")
def exports_page():
    """
    Render Data Export & Weather Intelligence Reports page.
    """
    return render_template("exports.html")


@app.route("/api/export/summary")
def api_export_summary():
    """
    Fetch live real-time export summary metrics matching filter criteria.
    """
    start_date = request.args.get("start_date", "")
    end_date = request.args.get("end_date", "")
    event_type = request.args.get("event_type", "all")
    state = request.args.get("state", "all")
    city = request.args.get("city", "")
    source = request.args.get("source", "all")
    verification_status = request.args.get("verification_status", "all")
    trust_level = request.args.get("trust_level", "all")

    success, metrics = fetch_export_summary_metrics(
        start_date=start_date,
        end_date=end_date,
        event_type=event_type,
        state=state,
        city=city,
        source=source,
        verification_status=verification_status,
        trust_level=trust_level
    )

    if success:
        return jsonify({"success": True, "data": metrics}), 200
    else:
        return jsonify({"success": False, "error": metrics}), 500


@app.route("/api/export/reports/csv")
def api_export_reports_csv():
    """
    Generate downloadable CSV file of filtered weather reports.
    """
    start_date = request.args.get("start_date", "")
    end_date = request.args.get("end_date", "")
    event_type = request.args.get("event_type", "all")
    state = request.args.get("state", "all")
    city = request.args.get("city", "")
    source = request.args.get("source", "all")
    verification_status = request.args.get("verification_status", "all")
    trust_level = request.args.get("trust_level", "all")

    success, records = fetch_filtered_reports_for_export(
        start_date, end_date, event_type, state, city, source, verification_status, trust_level
    )

    if not success:
        return jsonify({"success": False, "error": records}), 500

    output = io.StringIO()
    fieldnames = [
        "id", "source", "source_url", "report_text", "event_type", "report_datetime",
        "city", "state", "latitude", "longitude", "verification_result", "verification_score",
        "verification_reason", "trust_score", "trust_reason", "ai_confidence",
        "duplicate_status", "duplicate_similarity_score", "created_at"
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for row in records:
        writer.writerow(row)

    csv_data = output.getvalue()
    output.close()

    response = Response(csv_data, mimetype="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=weather_reports_export.csv"
    return response


@app.route("/api/export/reports/json")
def api_export_reports_json():
    """
    Generate downloadable JSON file of filtered weather reports.
    """
    start_date = request.args.get("start_date", "")
    end_date = request.args.get("end_date", "")
    event_type = request.args.get("event_type", "all")
    state = request.args.get("state", "all")
    city = request.args.get("city", "")
    source = request.args.get("source", "all")
    verification_status = request.args.get("verification_status", "all")
    trust_level = request.args.get("trust_level", "all")

    success, records = fetch_filtered_reports_for_export(
        start_date, end_date, event_type, state, city, source, verification_status, trust_level
    )

    if not success:
        return jsonify({"success": False, "error": records}), 500

    json_str = jsonify(records).get_data(as_text=True)
    response = Response(json_str, mimetype="application/json")
    response.headers["Content-Disposition"] = "attachment; filename=weather_reports_export.json"
    return response


@app.route("/api/export/weather/csv")
def api_export_weather_csv():
    """
    Generate downloadable CSV file of filtered weather observations (api_weather_data).
    """
    start_date = request.args.get("start_date", "")
    end_date = request.args.get("end_date", "")
    event_type = request.args.get("event_type", "all")
    state = request.args.get("state", "all")
    city = request.args.get("city", "")

    success, records = fetch_filtered_observations_for_export(
        start_date, end_date, event_type, state, city
    )

    if not success:
        return jsonify({"success": False, "error": records}), 500

    output = io.StringIO()
    fieldnames = [
        "city", "state", "latitude", "longitude", "temperature", "humidity",
        "wind_speed", "weather_condition", "weather_description", "event_type",
        "event_confidence", "recorded_at"
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for row in records:
        writer.writerow(row)

    csv_data = output.getvalue()
    output.close()

    response = Response(csv_data, mimetype="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=weather_observations_export.csv"
    return response


@app.route("/api/export/alerts/csv")
def api_export_alerts_csv():
    """
    Generate downloadable CSV file of weather alerts.
    """
    event_type = request.args.get("event_type", "all")
    severity = request.args.get("severity", "all")
    status = request.args.get("status", "all")
    state = request.args.get("state", "all")
    city = request.args.get("city", "")

    success, records = fetch_filtered_alerts_for_export(
        event_type, severity, status, state, city
    )

    if not success:
        return jsonify({"success": False, "error": records}), 500

    output = io.StringIO()
    fieldnames = [
        "alert_id", "event_type", "severity", "city", "state",
        "latitude", "longitude", "event_confidence", "status",
        "detected_at", "resolved_at"
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for row in records:
        writer.writerow(row)

    csv_data = output.getvalue()
    output.close()

    response = Response(csv_data, mimetype="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=weather_alerts_export.csv"
    return response


@app.route("/api/export/admin-audit/csv")
@admin_required
def api_export_admin_audit_csv():
    """
    Generate downloadable CSV file of admin verification audit trail history (Admin only).
    """
    success, records = fetch_admin_audit_for_export()
    if not success:
        return jsonify({"success": False, "error": records}), 500

    output = io.StringIO()
    fieldnames = [
        "action_id", "report_id", "action_type", "previous_verification",
        "new_verification", "reason", "performed_by", "action_datetime"
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for row in records:
        writer.writerow(row)

    csv_data = output.getvalue()
    output.close()

    response = Response(csv_data, mimetype="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=admin_audit_actions_export.csv"
    return response


@app.route("/api/intelligence-summary")
def api_intelligence_summary():
    """
    Generate structured summary from current PostgreSQL database tables.
    """
    success, data = generate_weather_intelligence_summary()
    if success:
        return jsonify({"success": True, "data": data}), 200
    else:
        return jsonify({"success": False, "error": data}), 500


@app.route("/api/export/intelligence-summary/download")
def api_download_intelligence_summary():
    """
    Generate downloadable text file of current Weather Intelligence Summary.
    """
    success, data = generate_weather_intelligence_summary()
    if not success:
        return jsonify({"success": False, "error": data}), 500

    lines = []
    lines.append("================================================================")
    lines.append("NATIONAL WEATHER INTELLIGENCE SUMMARY REPORT")
    lines.append(f"Generated At: {data['generated_at']}")
    lines.append("================================================================")
    lines.append("")
    lines.append("1. NATIONAL OVERVIEW")
    lines.append("----------------------------------------------------------------")
    ov = data["national_overview"]
    lines.append(f"Total Weather Reports Ingested:   {ov['total_reports']}")
    lines.append(f"Total API Weather Observations: {ov['total_observations']}")
    lines.append(f"Currently Active Weather Alerts:{ov['active_alerts']}")
    lines.append(f"States Represented in Dataset:  {ov['states_represented']}")
    lines.append(f"Cities Represented in Dataset:  {ov['cities_represented']}")
    lines.append(f"Average Source Trust Score:     {ov['average_trust_score']}%")
    lines.append("")
    lines.append("2. MAJOR WEATHER EVENTS")
    lines.append("----------------------------------------------------------------")
    lines.append("Top Weather Event Types:")
    for ev in data["major_events"]["most_common_events"]:
        lines.append(f"  - {ev['event_type']}: {ev['count']} occurrences")
    lines.append("")
    lines.append("Highest AI Confidence Detection Events:")
    for ev in data["major_events"]["highest_confidence_events"]:
        lines.append(f"  - {ev['city']} ({ev['state']}): {ev['event_type']} ({ev['max_conf']}% confidence)")
    lines.append("")
    lines.append("3. VERIFICATION & DATA QUALITY")
    lines.append("----------------------------------------------------------------")
    vo = data["verification_overview"]
    lines.append(f"Verified (Likely Consistent):   {vo['verified_reports']}")
    lines.append(f"Needs Verification:              {vo['needs_verification']}")
    lines.append(f"Suspicious Reports:             {vo['suspicious']}")
    lines.append(f"Unverified Reports:             {vo['unverified']}")
    dq = data["data_quality"]
    lines.append(f"Unique Reports:                 {dq['unique_reports']}")
    lines.append(f"Potential Duplicates:           {dq['potential_duplicates']}")
    lines.append("")
    lines.append("4. ALERT STATUS SUMMARY")
    lines.append("----------------------------------------------------------------")
    al = data["alert_status"]
    lines.append(f"Active Alerts:                  {al['active_alerts']} (High: {al['high_severity']}, Medium: {al['medium_severity']}, Low: {al['low_severity']})")
    lines.append(f"Resolved Alerts:                {al['resolved_alerts']}")
    lines.append("")
    lines.append("5. KEY OBSERVATIONS & FINDINGS")
    lines.append("----------------------------------------------------------------")
    for obs in data["key_observations"]:
        lines.append(f"  * {obs}")
    lines.append("")
    lines.append("================================================================")
    lines.append("END OF INTELLIGENCE REPORT")
    lines.append("================================================================")

    report_text = "\n".join(lines)
    response = Response(report_text, mimetype="text/plain")
    response.headers["Content-Disposition"] = "attachment; filename=national_weather_intelligence_summary.txt"
    return response


@app.errorhandler(404)
def page_not_found(e):
    """
    Handle 404 Not Found error safely.
    Returns JSON for /api/* requests or 404.html template for HTML requests.
    """
    if request.path.startswith("/api/"):
        return jsonify({"success": False, "error": "Requested API endpoint not found."}), 404
    return render_template("404.html"), 404


@app.errorhandler(500)
def internal_server_error(e):
    """
    Handle 500 Internal Server Error safely without leaking stack traces.
    Returns JSON for /api/* requests or 500.html template for HTML requests.
    """
    if request.path.startswith("/api/"):
        return jsonify({"success": False, "error": "Internal server processing error."}), 500
    return render_template("500.html"), 500


if __name__ == "__main__":
    socketio.run(app, debug=False, host="0.0.0.0", port=5000, allow_unsafe_werkzeug=True)
