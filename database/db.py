import os
import math
import psycopg2
from ml.weather_classifier import WeatherEventClassifier
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv, find_dotenv
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

from ml.weather_classifier import WeatherEventClassifier
from ml.report_verifier import ReportVerifier
from ml.duplicate_detector import DuplicateDetector
from ml.trust_scorer import SourceTrustScorer


def _reload_env():
    """Ensure environment variables from .env file are loaded with override."""
    env_file = find_dotenv()
    if env_file:
        load_dotenv(env_file, override=True)
    else:
        load_dotenv(override=True)


# Load env on module import
_reload_env()

CREATE_WEATHER_REPORTS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS weather_reports (
    id SERIAL PRIMARY KEY,
    source VARCHAR(100),
    source_url TEXT,
    report_text TEXT,
    event_type VARCHAR(50),
    report_datetime TIMESTAMP,
    city VARCHAR(100),
    state VARCHAR(100),
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    image_url TEXT,
    video_url TEXT,
    verification_status VARCHAR(30) DEFAULT 'Unverified',
    trust_score DECIMAL(5,2),
    ai_confidence DECIMAL(5,2),
    is_duplicate BOOLEAN DEFAULT FALSE,
    duplicate_group VARCHAR(100),
    verification_result VARCHAR(50),
    verification_score DECIMAL(5,2),
    verification_reason TEXT,
    verified_at TIMESTAMP,
    duplicate_status VARCHAR(50),
    duplicate_similarity_score DECIMAL(5,2),
    duplicate_reason TEXT,
    duplicate_checked_at TIMESTAMP,
    trust_reason TEXT,
    trust_updated_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

ALTER_WEATHER_REPORTS_COLUMNS_SQL = """
ALTER TABLE weather_reports ADD COLUMN IF NOT EXISTS verification_result VARCHAR(50);
ALTER TABLE weather_reports ADD COLUMN IF NOT EXISTS verification_score DECIMAL(5,2);
ALTER TABLE weather_reports ADD COLUMN IF NOT EXISTS verification_reason TEXT;
ALTER TABLE weather_reports ADD COLUMN IF NOT EXISTS verified_at TIMESTAMP;
ALTER TABLE weather_reports ADD COLUMN IF NOT EXISTS duplicate_status VARCHAR(50);
ALTER TABLE weather_reports ADD COLUMN IF NOT EXISTS duplicate_similarity_score DECIMAL(5,2);
ALTER TABLE weather_reports ADD COLUMN IF NOT EXISTS duplicate_reason TEXT;
ALTER TABLE weather_reports ADD COLUMN IF NOT EXISTS duplicate_checked_at TIMESTAMP;
ALTER TABLE weather_reports ADD COLUMN IF NOT EXISTS trust_score DECIMAL(5,2);
ALTER TABLE weather_reports ADD COLUMN IF NOT EXISTS trust_reason TEXT;
ALTER TABLE weather_reports ADD COLUMN IF NOT EXISTS trust_updated_at TIMESTAMP;
"""

CREATE_API_WEATHER_DATA_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS api_weather_data (
    id SERIAL PRIMARY KEY,
    source VARCHAR(100) DEFAULT 'OpenWeatherMap API',
    city VARCHAR(100),
    state VARCHAR(100),
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    temperature DOUBLE PRECISION,
    humidity DOUBLE PRECISION,
    wind_speed DOUBLE PRECISION,
    weather_condition VARCHAR(50),
    weather_description TEXT,
    recorded_at TIMESTAMP,
    event_type VARCHAR(50),
    event_confidence DECIMAL(5,2),
    classified_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

ALTER_API_WEATHER_DATA_COLUMNS_SQL = """
ALTER TABLE api_weather_data ADD COLUMN IF NOT EXISTS event_type VARCHAR(50);
ALTER TABLE api_weather_data ADD COLUMN IF NOT EXISTS event_confidence DECIMAL(5,2);
ALTER TABLE api_weather_data ADD COLUMN IF NOT EXISTS classified_at TIMESTAMP;
"""

CREATE_INDEXES_SQL = """
CREATE INDEX IF NOT EXISTS idx_wr_event_type ON weather_reports(event_type);
CREATE INDEX IF NOT EXISTS idx_wr_state ON weather_reports(state);
CREATE INDEX IF NOT EXISTS idx_wr_city ON weather_reports(city);
CREATE INDEX IF NOT EXISTS idx_wr_source ON weather_reports(source);
CREATE INDEX IF NOT EXISTS idx_wr_datetime ON weather_reports(report_datetime);
CREATE INDEX IF NOT EXISTS idx_wr_verification ON weather_reports(verification_result);
CREATE INDEX IF NOT EXISTS idx_wr_trust_score ON weather_reports(trust_score);
CREATE INDEX IF NOT EXISTS idx_wr_duplicate ON weather_reports(duplicate_status);
"""

CREATE_USERS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) DEFAULT 'user',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_ADMIN_ACTIONS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS admin_actions (
    id SERIAL PRIMARY KEY,
    report_id INT NOT NULL REFERENCES weather_reports(id) ON DELETE CASCADE,
    action_type VARCHAR(50) NOT NULL,
    previous_verification VARCHAR(50),
    new_verification VARCHAR(50),
    reason TEXT,
    performed_by VARCHAR(100) DEFAULT 'Admin',
    action_datetime TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_WEATHER_ALERTS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS weather_alerts (
    id SERIAL PRIMARY KEY,
    weather_observation_id INT REFERENCES api_weather_data(id) ON DELETE CASCADE,
    event_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    city VARCHAR(100) NOT NULL,
    state VARCHAR(100),
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    event_confidence DECIMAL(5,2),
    status VARCHAR(20) DEFAULT 'Active',
    source VARCHAR(100) DEFAULT 'Automated System',
    title TEXT,
    description TEXT,
    link TEXT,
    guid VARCHAR(255),
    instruction TEXT,
    publisher VARCHAR(150),
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

ALTER_WEATHER_ALERTS_COLUMNS_SQL = """
ALTER TABLE weather_alerts ADD COLUMN IF NOT EXISTS source VARCHAR(100) DEFAULT 'Automated System';
ALTER TABLE weather_alerts ADD COLUMN IF NOT EXISTS title TEXT;
ALTER TABLE weather_alerts ADD COLUMN IF NOT EXISTS description TEXT;
ALTER TABLE weather_alerts ADD COLUMN IF NOT EXISTS link TEXT;
ALTER TABLE weather_alerts ADD COLUMN IF NOT EXISTS guid VARCHAR(255);
ALTER TABLE weather_alerts ADD COLUMN IF NOT EXISTS instruction TEXT;
ALTER TABLE weather_alerts ADD COLUMN IF NOT EXISTS publisher VARCHAR(150);
"""

CREATE_ALERT_INDEXES_SQL = """
CREATE INDEX IF NOT EXISTS idx_alerts_event ON weather_alerts(event_type);
CREATE INDEX IF NOT EXISTS idx_alerts_city ON weather_alerts(city);
CREATE INDEX IF NOT EXISTS idx_alerts_state ON weather_alerts(state);
CREATE INDEX IF NOT EXISTS idx_alerts_severity ON weather_alerts(severity);
CREATE INDEX IF NOT EXISTS idx_alerts_status ON weather_alerts(status);
CREATE UNIQUE INDEX IF NOT EXISTS idx_alerts_guid ON weather_alerts(guid) WHERE guid IS NOT NULL;
"""



def _seed_default_users(cursor):
    """Seed default admin, analyst, and user accounts if they do not exist."""
    users_to_seed = [
        ("admin", generate_password_hash("admin123"), "admin"),
        ("analyst", generate_password_hash("analyst123"), "analyst"),
        ("demo_user", generate_password_hash("user123"), "user")
    ]
    for username, pwd_hash, role in users_to_seed:
        cursor.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s) ON CONFLICT (username) DO NOTHING;",
            (username, pwd_hash, role)
        )



def get_db_connection():
    """
    Establish and return a connection to the PostgreSQL database.
    """
    _reload_env()

    database_url = os.getenv("DATABASE_URL")

    if database_url:
        return psycopg2.connect(database_url)

    host = os.getenv("DB_HOST") or os.getenv("POSTGRES_HOST") or os.getenv("PGHOST") or "localhost"
    port = os.getenv("DB_PORT") or os.getenv("POSTGRES_PORT") or os.getenv("PGPORT") or "5432"
    dbname = os.getenv("DB_NAME") or os.getenv("POSTGRES_DB") or os.getenv("PGDATABASE") or "national_weather"
    user = os.getenv("DB_USER") or os.getenv("POSTGRES_USER") or os.getenv("PGUSER") or "postgres"
    password = os.getenv("DB_PASSWORD") or os.getenv("POSTGRES_PASSWORD") or os.getenv("PGPASSWORD") or ""

    try:
        return psycopg2.connect(
            host=host,
            port=port,
            dbname=dbname,
            user=user,
            password=password
        )
    except Exception as primary_err:
        if host == "localhost":
            try:
                return psycopg2.connect(
                    host="127.0.0.1",
                    port=port,
                    dbname=dbname,
                    user=user,
                    password=password
                )
            except Exception:
                raise primary_err
        raise primary_err


def test_db_connection():
    """
    Test PostgreSQL connection with password sanitization.
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        db_version = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        return True, db_version
    except Exception as e:
        if conn:
            try:
                conn.close()
            except Exception:
                pass

        error_msg = str(e)
        password = os.getenv("DB_PASSWORD") or os.getenv("POSTGRES_PASSWORD") or os.getenv("PGPASSWORD") or ""
        if password and password in error_msg:
            error_msg = error_msg.replace(password, "******")

        return False, error_msg


def init_db():
    """
    Initialize database schema by creating required tables and executing column migrations.
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(CREATE_WEATHER_REPORTS_TABLE_SQL)
        cursor.execute(ALTER_WEATHER_REPORTS_COLUMNS_SQL)
        cursor.execute(CREATE_API_WEATHER_DATA_TABLE_SQL)
        cursor.execute(ALTER_API_WEATHER_DATA_COLUMNS_SQL)
        cursor.execute(CREATE_INDEXES_SQL)
        cursor.execute(CREATE_USERS_TABLE_SQL)
        cursor.execute(CREATE_ADMIN_ACTIONS_TABLE_SQL)
        cursor.execute(CREATE_WEATHER_ALERTS_TABLE_SQL)
        cursor.execute(ALTER_WEATHER_ALERTS_COLUMNS_SQL)
        cursor.execute(CREATE_ALERT_INDEXES_SQL)
        _seed_default_users(cursor)
        conn.commit()
        cursor.close()
        conn.close()
        return True, "Database initialized successfully."
    except Exception as e:
        if conn:
            try:
                conn.close()
            except Exception:
                pass

        error_msg = str(e)
        password = os.getenv("DB_PASSWORD") or os.getenv("POSTGRES_PASSWORD") or os.getenv("PGPASSWORD") or ""
        if password and password in error_msg:
            error_msg = error_msg.replace(password, "******")

        return False, error_msg


def fetch_latest_obs_for_city(city_name):
    """
    Fetch the most recent observation record from api_weather_data matching city_name.
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            "SELECT * FROM api_weather_data WHERE LOWER(city) = LOWER(%s) ORDER BY created_at DESC LIMIT 1;",
            (city_name.strip(),)
        )
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        return row
    except Exception:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        return None


def fetch_recent_citizen_reports(hours=24):
    """
    Fetch citizen reports submitted within the last N hours for duplicate detection comparisons.
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            "SELECT * FROM weather_reports WHERE created_at >= NOW() - INTERVAL '%s hours' ORDER BY created_at DESC;",
            (hours,)
        )
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return rows
    except Exception:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        return []


def insert_citizen_report(report_text, event_type, city, state, latitude=None, longitude=None, report_datetime=None, image_url=None, video_url=None):
    """
    Insert a citizen submitted weather report into weather_reports table.
    Automatically performs:
    1. AI Verification Analysis against recent api_weather_data
    2. Multi-Signal Duplicate & Related Report Detection
    3. Source Trust Scoring calculation
    """
    conn = None
    try:
        lat_val = float(latitude) if latitude and str(latitude).strip() != '' else None
        lon_val = float(longitude) if longitude and str(longitude).strip() != '' else None

        parsed_dt = None
        if report_datetime and str(report_datetime).strip() != '':
            try:
                parsed_dt = datetime.fromisoformat(str(report_datetime).strip())
            except ValueError:
                parsed_dt = datetime.now()
        else:
            parsed_dt = datetime.now()

        source_name = 'Citizen Report'

        # 1. AI Verification Analysis
        recent_obs = fetch_latest_obs_for_city(city)
        v_result, v_score, v_reason, v_at = ReportVerifier.verify_report(
            report_text=report_text,
            event_type=event_type,
            city=city,
            report_datetime=parsed_dt,
            recent_obs=recent_obs
        )

        # 2. Duplicate Detection
        new_report_payload = {
            "city": city,
            "state": state,
            "event_type": event_type,
            "report_text": report_text,
            "latitude": lat_val,
            "longitude": lon_val,
            "report_datetime": parsed_dt
        }
        recent_citizen_reps = fetch_recent_citizen_reports(hours=24)
        is_dup, dup_grp, dup_status, dup_sim, dup_reason, dup_checked = DuplicateDetector.detect_duplicates(
            new_report=new_report_payload,
            recent_reports=recent_citizen_reps
        )

        # 3. Source Trust Scoring Calculation
        t_score, t_level, t_reason, t_updated = SourceTrustScorer.calculate_trust(
            source=source_name,
            verification_result=v_result,
            verification_score=v_score,
            duplicate_status=dup_status,
            latitude=lat_val,
            longitude=lon_val,
            report_datetime=parsed_dt,
            image_url=image_url
        )

        conn = get_db_connection()
        cursor = conn.cursor()

        sql = """
        INSERT INTO weather_reports (
            source,
            report_text,
            event_type,
            city,
            state,
            latitude,
            longitude,
            report_datetime,
            image_url,
            video_url,
            verification_status,
            trust_score,
            ai_confidence,
            is_duplicate,
            duplicate_group,
            verification_result,
            verification_score,
            verification_reason,
            verified_at,
            duplicate_status,
            duplicate_similarity_score,
            duplicate_reason,
            duplicate_checked_at,
            trust_reason,
            trust_updated_at
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        ) RETURNING id;
        """

        cursor.execute(sql, (
            source_name,
            report_text,
            event_type,
            city,
            state,
            lat_val,
            lon_val,
            parsed_dt,
            image_url if image_url and image_url.strip() else None,
            video_url if video_url and video_url.strip() else None,
            v_result,
            t_score,
            v_score,
            is_dup,
            dup_grp,
            v_result,
            v_score,
            v_reason,
            v_at,
            dup_status,
            dup_sim,
            dup_reason,
            dup_checked,
            t_reason,
            t_updated
        ))

        new_id = cursor.fetchone()[0]
        conn.commit()
        cursor.close()
        conn.close()
        return True, new_id
    except Exception as e:
        if conn:
            try:
                conn.close()
            except Exception:
                pass

        error_msg = str(e)
        password = os.getenv("DB_PASSWORD") or os.getenv("POSTGRES_PASSWORD") or os.getenv("PGPASSWORD") or ""
        if password and password in error_msg:
            error_msg = error_msg.replace(password, "******")

        return False, error_msg


def analyze_and_update_report(report_id):
    """
    Manually trigger AI verification, duplicate analysis, and source trust scoring re-analysis for a report by ID.
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM weather_reports WHERE id = %s;", (report_id,))
        report = cursor.fetchone()

        if not report:
            cursor.close()
            conn.close()
            return False, "Report not found."

        city = report.get("city", "")
        recent_obs = fetch_latest_obs_for_city(city)

        v_result, v_score, v_reason, v_at = ReportVerifier.verify_report(
            report_text=report.get("report_text"),
            event_type=report.get("event_type"),
            city=city,
            report_datetime=report.get("report_datetime"),
            recent_obs=recent_obs
        )

        recent_reps = fetch_recent_citizen_reports(hours=24)
        is_dup, dup_grp, dup_status, dup_sim, dup_reason, dup_checked = DuplicateDetector.detect_duplicates(
            new_report=report,
            recent_reports=recent_reps
        )

        t_score, t_level, t_reason, t_updated = SourceTrustScorer.calculate_trust(
            source=report.get("source", "Citizen Report"),
            verification_result=v_result,
            verification_score=v_score,
            duplicate_status=dup_status,
            latitude=report.get("latitude"),
            longitude=report.get("longitude"),
            report_datetime=report.get("report_datetime"),
            image_url=report.get("image_url")
        )

        update_cursor = conn.cursor()
        update_cursor.execute("""
            UPDATE weather_reports 
            SET verification_status = %s,
                trust_score = %s,
                ai_confidence = %s,
                verification_result = %s,
                verification_score = %s,
                verification_reason = %s,
                verified_at = %s,
                is_duplicate = %s,
                duplicate_group = %s,
                duplicate_status = %s,
                duplicate_similarity_score = %s,
                duplicate_reason = %s,
                duplicate_checked_at = %s,
                trust_reason = %s,
                trust_updated_at = %s
            WHERE id = %s;
        """, (
            v_result, t_score, v_score, v_result, v_score, v_reason, v_at,
            is_dup, dup_grp, dup_status, dup_sim, dup_reason, dup_checked,
            t_reason, t_updated, report_id
        ))

        conn.commit()
        update_cursor.close()
        cursor.close()
        conn.close()

        return True, {
            "id": report_id,
            "verification_result": v_result,
            "verification_score": v_score,
            "duplicate_status": dup_status,
            "trust_score": t_score,
            "trust_level": t_level
        }
    except Exception as e:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        return False, str(e)


def fetch_all_reports(status_filter=None, duplicate_filter=None, trust_filter=None, source_filter=None):
    """
    Fetch records from weather_reports table with optional verification, duplicate, trust level, and source filtering.
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        query = "SELECT * FROM weather_reports WHERE 1=1"
        params = []

        if status_filter and status_filter.strip() and status_filter.strip() != "All":
            query += " AND (verification_result = %s OR verification_status = %s)"
            params.extend([status_filter.strip(), status_filter.strip()])

        if duplicate_filter and duplicate_filter.strip() and duplicate_filter.strip() != "All":
            query += " AND duplicate_status = %s"
            params.append(duplicate_filter.strip())

        if trust_filter and trust_filter.strip() and trust_filter.strip() != "All":
            if trust_filter == "High Trust":
                query += " AND trust_score >= 80.0"
            elif trust_filter == "Medium Trust":
                query += " AND trust_score >= 50.0 AND trust_score < 80.0"
            elif trust_filter == "Low Trust":
                query += " AND trust_score < 50.0"

        if source_filter and source_filter.strip() and source_filter.strip() != "All":
            query += " AND (source = %s OR source ILIKE %s)"
            params.extend([source_filter.strip(), f"%{source_filter.strip()}%"])

        query += " ORDER BY created_at DESC;"

        cursor.execute(query, tuple(params))
        reports = cursor.fetchall()
        cursor.close()
        conn.close()
        return True, reports
    except Exception as e:
        if conn:
            try:
                conn.close()
            except Exception:
                pass

        error_msg = str(e)
        password = os.getenv("DB_PASSWORD") or os.getenv("POSTGRES_PASSWORD") or os.getenv("PGPASSWORD") or ""
        if password and password in error_msg:
            error_msg = error_msg.replace(password, "******")

        return False, error_msg


def search_weather_reports(
    keyword=None,
    event_type=None,
    state=None,
    city=None,
    source=None,
    verification=None,
    trust_level=None,
    duplicate_status=None,
    date_from=None,
    date_to=None,
    sort_by="date_desc",
    page=1,
    per_page=20
):
    """
    Perform advanced parameterized searching, multi-filter aggregation, sorting, and pagination 
    against PostgreSQL weather_reports table.
    """
    conn = None
    try:
        page_num = max(1, int(page)) if page and str(page).isdigit() else 1
        per_page_num = max(1, min(100, int(per_page))) if per_page and str(per_page).isdigit() else 20

        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        where_clauses = ["1=1"]
        params = []

        # 1. Keyword search (searches report_text, city, state, source, event_type)
        if keyword and str(keyword).strip():
            kw = f"%{str(keyword).strip()}%"
            where_clauses.append(
                "(report_text ILIKE %s OR city ILIKE %s OR state ILIKE %s OR source ILIKE %s OR event_type ILIKE %s)"
            )
            params.extend([kw, kw, kw, kw, kw])

        # 2. Event Type Filter
        if event_type and str(event_type).strip() and str(event_type).strip() != "All":
            ev = str(event_type).strip()
            where_clauses.append("(event_type = %s OR event_type ILIKE %s)")
            params.extend([ev, f"%{ev}%"])

        # 3. State Filter
        if state and str(state).strip() and str(state).strip() != "All":
            where_clauses.append("(state = %s OR state ILIKE %s)")
            params.extend([str(state).strip(), f"%{str(state).strip()}%"])

        # 4. City Filter
        if city and str(city).strip():
            where_clauses.append("(city = %s OR city ILIKE %s)")
            params.extend([str(city).strip(), f"%{str(city).strip()}%"])

        # 5. Source Filter
        if source and str(source).strip() and str(source).strip() != "All":
            src = str(source).strip()
            where_clauses.append("(source = %s OR source ILIKE %s)")
            params.extend([src, f"%{src}%"])

        # 6. Verification Status Filter
        if verification and str(verification).strip() and str(verification).strip() != "All":
            v_val = str(verification).strip()
            if v_val in ["Verified", "Likely Consistent"]:
                where_clauses.append("(verification_result = 'Likely Consistent' OR verification_status = 'Likely Consistent')")
            elif v_val == "Needs Verification":
                where_clauses.append("(verification_result = 'Needs Verification' OR verification_status = 'Needs Verification' OR (verification_result IS NULL AND (verification_status IS NULL OR verification_status = 'Unverified')))")
            elif v_val == "Suspicious":
                where_clauses.append("(verification_result = 'Suspicious' OR verification_status = 'Suspicious')")
            elif v_val == "Unverified":
                where_clauses.append("(verification_result IS NULL OR verification_result = 'Unverified' OR verification_status = 'Unverified')")
            else:
                where_clauses.append("(verification_result = %s OR verification_status = %s)")
                params.extend([v_val, v_val])

        # 7. Trust Level Filter
        if trust_level and str(trust_level).strip() and str(trust_level).strip() != "All":
            t_val = str(trust_level).strip()
            if t_val in ["High Trust", "High Trust (80–100)", "High Trust (80-100)"]:
                where_clauses.append("trust_score >= 80.0")
            elif t_val in ["Medium Trust", "Medium Trust (50–79)", "Medium Trust (50-79)"]:
                where_clauses.append("trust_score >= 50.0 AND trust_score < 80.0")
            elif t_val in ["Low Trust", "Low Trust (0–49)", "Low Trust (0-49)"]:
                where_clauses.append("(trust_score < 50.0 OR trust_score IS NULL)")

        # 8. Duplicate Status Filter
        if duplicate_status and str(duplicate_status).strip() and str(duplicate_status).strip() != "All":
            d_val = str(duplicate_status).strip()
            if d_val == "Unique":
                where_clauses.append("(duplicate_status = 'Unique' OR duplicate_status IS NULL OR is_duplicate = FALSE)")
            elif d_val == "Related Report":
                where_clauses.append("duplicate_status = 'Related Report'")
            elif d_val in ["Potential Duplicate", "Duplicates"]:
                where_clauses.append("(duplicate_status = 'Potential Duplicate' OR is_duplicate = TRUE)")
            else:
                where_clauses.append("duplicate_status = %s")
                params.append(d_val)

        # 9. Date From & Date To Filter
        if date_from and str(date_from).strip():
            where_clauses.append("(report_datetime >= %s OR created_at >= %s)")
            dt_from_str = str(date_from).strip() + " 00:00:00"
            params.extend([dt_from_str, dt_from_str])

        if date_to and str(date_to).strip():
            where_clauses.append("(report_datetime <= %s OR created_at <= %s)")
            dt_to_str = str(date_to).strip() + " 23:59:59"
            params.extend([dt_to_str, dt_to_str])

        where_sql = " AND ".join(where_clauses)

        # Count total matching records
        count_sql = f"SELECT COUNT(*) as total FROM weather_reports WHERE {where_sql};"
        cursor.execute(count_sql, tuple(params))
        total_row = cursor.fetchone()
        total = total_row["total"] if total_row else 0
        total_pages = max(1, math.ceil(total / per_page_num)) if total > 0 else 1

        # 10. Whitelisted Server-Side Sorting
        sort_map = {
            "date_desc": "COALESCE(report_datetime, created_at) DESC, id DESC",
            "date_asc": "COALESCE(report_datetime, created_at) ASC, id ASC",
            "trust_desc": "COALESCE(trust_score, 0) DESC, id DESC",
            "trust_asc": "COALESCE(trust_score, 0) ASC, id ASC",
            "confidence_desc": "COALESCE(ai_confidence, 0) DESC, id DESC"
        }
        order_by_clause = sort_map.get(str(sort_by).strip(), sort_map["date_desc"])

        offset = (page_num - 1) * per_page_num
        query_sql = f"""
            SELECT * FROM weather_reports 
            WHERE {where_sql} 
            ORDER BY {order_by_clause} 
            LIMIT %s OFFSET %s;
        """
        query_params = list(params) + [per_page_num, offset]
        cursor.execute(query_sql, tuple(query_params))
        reports = cursor.fetchall()

        for r in reports:
            r["attention_level"] = _calculate_attention_level(r)

        cursor.close()
        conn.close()

        return True, {
            "reports": reports,
            "page": page_num,
            "per_page": per_page_num,
            "total": total,
            "total_pages": total_pages
        }
    except Exception as e:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        return False, str(e)


def fetch_report_by_id(report_id):
    """
    Fetch a single weather report record by ID for detail view.
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM weather_reports WHERE id = %s;", (report_id,))
        report = cursor.fetchone()
        cursor.close()
        conn.close()
        if report:
            return True, report
        return False, "Report not found."
    except Exception as e:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        return False, str(e)


def authenticate_user(username, password):
    """
    Authenticate user against users table using werkzeug check_password_hash.
    Returns (True, user_dict) or (False, error_message).
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM users WHERE username = %s;", (username.strip(),))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user and check_password_hash(user["password_hash"], password):
            return True, {
                "id": user["id"],
                "username": user["username"],
                "role": user["role"]
            }
        return False, "Invalid username or password."
    except Exception as e:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        return False, str(e)


def fetch_admin_summary():
    """
    Fetch aggregated counters for Admin Dashboard.
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        summary = {
            "total_reports": 0,
            "unverified_reports": 0,
            "needs_verification": 0,
            "suspicious_reports": 0,
            "verified_reports": 0,
            "potential_duplicates": 0,
            "average_trust_score": 0.0
        }

        cursor.execute("SELECT COUNT(*) as total FROM weather_reports;")
        summary["total_reports"] = cursor.fetchone()["total"]

        cursor.execute("SELECT COUNT(*) as cnt FROM weather_reports WHERE verification_result = 'Unverified' OR verification_status = 'Unverified' OR (verification_result IS NULL AND (verification_status IS NULL OR verification_status = 'Unverified'));")
        summary["unverified_reports"] = cursor.fetchone()["cnt"]

        cursor.execute("SELECT COUNT(*) as cnt FROM weather_reports WHERE verification_result = 'Needs Verification' OR verification_status = 'Needs Verification';")
        summary["needs_verification"] = cursor.fetchone()["cnt"]

        cursor.execute("SELECT COUNT(*) as cnt FROM weather_reports WHERE verification_result = 'Suspicious' OR verification_status = 'Suspicious';")
        summary["suspicious_reports"] = cursor.fetchone()["cnt"]

        cursor.execute("SELECT COUNT(*) as cnt FROM weather_reports WHERE verification_result IN ('Verified', 'Likely Consistent') OR verification_status IN ('Verified', 'Likely Consistent');")
        summary["verified_reports"] = cursor.fetchone()["cnt"]

        cursor.execute("SELECT COUNT(*) as cnt FROM weather_reports WHERE duplicate_status = 'Potential Duplicate' OR is_duplicate = TRUE;")
        summary["potential_duplicates"] = cursor.fetchone()["cnt"]

        cursor.execute("SELECT AVG(trust_score) as avg_score FROM weather_reports WHERE trust_score IS NOT NULL;")
        row = cursor.fetchone()
        summary["average_trust_score"] = round(float(row["avg_score"]), 1) if row and row["avg_score"] is not None else 0.0

        cursor.close()
        conn.close()
        return True, summary
    except Exception as e:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        return False, str(e)


def _calculate_attention_level(report):
    """
    Calculate report attention priority level (HIGH, MEDIUM, LOW).
    """
    v_res = str(report.get("verification_result") or report.get("verification_status") or "Unverified")
    t_score = float(report.get("trust_score") or 50.0)
    dup_stat = str(report.get("duplicate_status") or "")
    dup_sim = float(report.get("duplicate_similarity_score") or 0.0)
    event = str(report.get("event_type") or "")

    if (
        v_res == "Suspicious"
        or t_score < 40.0
        or (dup_stat == "Potential Duplicate" and dup_sim >= 80.0)
        or (event in ["Flood Risk", "Heavy Rainfall", "Heatwave", "Dust Storm"] and v_res in ["Needs Verification", "Unverified"])
    ):
        return "HIGH"
    elif (
        v_res in ["Needs Verification", "Unverified"]
        or (40.0 <= t_score < 70.0)
        or dup_stat == "Potential Duplicate"
    ):
        return "MEDIUM"
    else:
        return "LOW"


def fetch_admin_report_details(report_id):
    """
    Fetch full detail object for admin review, including matching OpenWeather API observation evidence, 
    duplicate group reports, and action audit history.
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute("SELECT * FROM weather_reports WHERE id = %s;", (report_id,))
        report = cursor.fetchone()
        if not report:
            cursor.close()
            conn.close()
            return False, "Report not found."

        # Fetch latest OpenWeather API observation for the city
        latest_obs = None
        if report.get("city"):
            cursor.execute(
                "SELECT * FROM api_weather_data WHERE LOWER(city) = LOWER(%s) ORDER BY recorded_at DESC, created_at DESC LIMIT 1;",
                (report["city"].strip(),)
            )
            latest_obs = cursor.fetchone()

        # Fetch duplicate/related group reports if applicable
        related_reports = []
        if report.get("duplicate_group"):
            cursor.execute(
                "SELECT id, source, city, state, event_type, report_datetime, duplicate_status, duplicate_similarity_score FROM weather_reports WHERE duplicate_group = %s AND id != %s ORDER BY id DESC LIMIT 5;",
                (report["duplicate_group"], report_id)
            )
            related_reports = cursor.fetchall()

        # Fetch action history for this report
        cursor.execute(
            "SELECT * FROM admin_actions WHERE report_id = %s ORDER BY action_datetime DESC;",
            (report_id,)
        )
        action_history = cursor.fetchall()

        cursor.close()
        conn.close()

        return True, {
            "report": report,
            "latest_obs": latest_obs,
            "related_reports": related_reports,
            "action_history": action_history,
            "attention_level": _calculate_attention_level(report)
        }
    except Exception as e:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        return False, str(e)


def update_report_verification(report_id, new_verification, reason, action_type="Updated Verification", performed_by="Admin"):
    """
    Update verification status/result in weather_reports, recalculate trust score using SourceTrustScorer,
    and insert audit entry into admin_actions table.
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute("SELECT * FROM weather_reports WHERE id = %s;", (report_id,))
        report = cursor.fetchone()
        if not report:
            cursor.close()
            conn.close()
            return False, "Report not found."

        old_verification = report.get("verification_result") or report.get("verification_status") or "Unverified"
        v_score = 90.0 if new_verification in ["Verified", "Likely Consistent"] else (30.0 if new_verification == "Suspicious" else 50.0)

        # Recalculate Trust Score using SourceTrustScorer
        t_score, t_level, t_reason, t_updated = SourceTrustScorer.calculate_trust(
            source=report.get("source", "Citizen Report"),
            verification_result=new_verification,
            verification_score=v_score,
            duplicate_status=report.get("duplicate_status"),
            latitude=report.get("latitude"),
            longitude=report.get("longitude"),
            report_datetime=report.get("report_datetime"),
            image_url=report.get("image_url")
        )

        now = datetime.now()
        updated_reason = reason.strip() if reason and reason.strip() else f"Manual admin review: marked as {new_verification}."

        # Update weather_reports
        cursor.execute("""
            UPDATE weather_reports 
            SET verification_status = %s,
                verification_result = %s,
                verification_score = %s,
                verification_reason = %s,
                verified_at = %s,
                trust_score = %s,
                trust_reason = %s,
                trust_updated_at = %s
            WHERE id = %s;
        """, (
            new_verification, new_verification, v_score, updated_reason, now,
            t_score, t_reason, now, report_id
        ))

        # Insert audit log into admin_actions
        cursor.execute("""
            INSERT INTO admin_actions (
                report_id, action_type, previous_verification, new_verification, reason, performed_by, action_datetime
            ) VALUES (%s, %s, %s, %s, %s, %s, %s);
        """, (
            report_id, action_type, old_verification, new_verification, updated_reason, performed_by, now
        ))

        conn.commit()
        cursor.close()
        conn.close()

        return True, {
            "id": report_id,
            "previous_verification": old_verification,
            "new_verification": new_verification,
            "trust_score": t_score,
            "verified_at": now.isoformat()
        }
    except Exception as e:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        return False, str(e)


def fetch_admin_action_history(page=1, per_page=20):
    """
    Fetch paginated audit log entries from admin_actions table.
    """
    conn = None
    try:
        page_num = max(1, int(page)) if page and str(page).isdigit() else 1
        per_page_num = max(1, min(100, int(per_page))) if per_page and str(per_page).isdigit() else 20

        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute("SELECT COUNT(*) as total FROM admin_actions;")
        total = cursor.fetchone()["total"]
        total_pages = max(1, math.ceil(total / per_page_num)) if total > 0 else 1

        offset = (page_num - 1) * per_page_num
        cursor.execute("""
            SELECT a.*, r.source, r.city, r.event_type 
            FROM admin_actions a 
            LEFT JOIN weather_reports r ON a.report_id = r.id 
            ORDER BY a.action_datetime DESC 
            LIMIT %s OFFSET %s;
        """, (per_page_num, offset))
        actions = cursor.fetchall()

        cursor.close()
        conn.close()

        return True, {
            "actions": actions,
            "page": page_num,
            "per_page": per_page_num,
            "total": total,
            "total_pages": total_pages
        }
    except Exception as e:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        return False, str(e)


def fetch_multi_source_summary():
    """
    Fetch summary counters and source distribution data for Multi-Source Weather Report Ingestion.
    """
    conn = None
    summary = {
        "total_reports": 0,
        "official_api_reports": 0,
        "citizen_reports": 0,
        "social_media_reports": 0,
        "news_reports": 0,
        "public_dataset_reports": 0,
        "govt_reports": 0,
        "verified_org_reports": 0,
        "chart_labels": ["Official API", "Govt/Official", "Verified Org", "News Website", "Citizen Report", "Social Media", "Public Dataset", "Unknown"],
        "chart_counts": [0, 0, 0, 0, 0, 0, 0, 0],
        "recent_reports": []
    }
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute("SELECT COUNT(*) as total FROM weather_reports;")
        t_row = cursor.fetchone()
        weather_report_count = t_row["total"] if t_row else 0

        cursor.execute("SELECT COUNT(*) as total FROM api_weather_data;")
        api_row = cursor.fetchone()
        api_report_count = api_row["total"] if api_row else 0

        cursor.execute("""
            SELECT COALESCE(source, 'Citizen Report') as source_name, COUNT(*) as count
            FROM weather_reports
            GROUP BY COALESCE(source, 'Citizen Report');
        """)
        rows = cursor.fetchall()
        source_counts = {r["source_name"]: r["count"] for r in rows}

        official_api_from_wr = 0
        govt_cnt = 0
        verified_org_cnt = 0
        news_cnt = 0
        citizen_cnt = 0
        social_cnt = 0
        public_data_cnt = 0
        unknown_cnt = 0

        for source_name, count in source_counts.items():
            s_lower = str(source_name).lower().strip()
            if any(k in s_lower for k in ["official weather api", "openweather", "api station sync"]):
                official_api_from_wr += count
            elif any(k in s_lower for k in ["government", "govt", "imd"]):
                govt_cnt += count
            elif any(k in s_lower for k in ["verified organization", "verified org", "skymet", "ndrf"]):
                verified_org_cnt += count
            elif any(k in s_lower for k in ["news website", "news report", "news"]):
                news_cnt += count
            elif any(k in s_lower for k in ["social media", "twitter", "mastodon", "x.com"]):
                social_cnt += count
            elif any(k in s_lower for k in ["public dataset", "open government data", "data archive"]):
                public_data_cnt += count
            elif "citizen" in s_lower or s_lower in ["user", "ground report"]:
                citizen_cnt += count
            else:
                unknown_cnt += count

        summary["total_reports"] = weather_report_count + api_report_count
        summary["official_api_reports"] = api_report_count + official_api_from_wr
        summary["govt_reports"] = govt_cnt
        summary["verified_org_reports"] = verified_org_cnt
        summary["news_reports"] = news_cnt
        summary["citizen_reports"] = citizen_cnt
        summary["social_media_reports"] = social_cnt
        summary["public_dataset_reports"] = public_data_cnt

        summary["chart_counts"] = [
            summary["official_api_reports"],
            summary["govt_reports"],
            summary["verified_org_reports"],
            summary["news_reports"],
            summary["citizen_reports"],
            summary["social_media_reports"],
            summary["public_dataset_reports"],
            unknown_cnt
        ]

        cursor.execute("SELECT * FROM weather_reports ORDER BY created_at DESC LIMIT 10;")
        recent = cursor.fetchall()

        if not recent and api_report_count > 0:
            cursor.execute("SELECT * FROM api_weather_data ORDER BY created_at DESC LIMIT 10;")
            api_recent = cursor.fetchall()
            recent = []
            for item in api_recent:
                recent.append({
                    "id": item.get("id"),
                    "source": "Official Weather API",
                    "city": item.get("city"),
                    "state": "-",
                    "event_type": item.get("event_type") or item.get("weather_condition") or "Weather Observation",
                    "verification_result": "Likely Consistent",
                    "verification_status": "Likely Consistent",
                    "trust_score": 95.0,
                    "report_datetime": item.get("recorded_at") or item.get("created_at"),
                    "created_at": item.get("created_at")
                })

        summary["recent_reports"] = recent

        cursor.close()
        conn.close()
        return True, summary
    except Exception:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        return False, summary



def fetch_report_verification_summary():
    """
    Fetch summary counters for citizen report verification results.
    """
    conn = None
    summary = {
        "Total Citizen Reports": 0,
        "Likely Consistent": 0,
        "Needs Verification": 0,
        "Suspicious": 0,
        "Unverified": 0
    }
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute("SELECT COUNT(*) as total FROM weather_reports;")
        t_row = cursor.fetchone()
        if t_row:
            summary["Total Citizen Reports"] = t_row["total"]

        cursor.execute("""
            SELECT COALESCE(verification_result, verification_status, 'Unverified') as result, COUNT(*) as count
            FROM weather_reports
            GROUP BY COALESCE(verification_result, verification_status, 'Unverified');
        """)
        rows = cursor.fetchall()

        for r in rows:
            res_key = r.get("result")
            cnt = r.get("count", 0)
            if res_key in summary:
                summary[res_key] = cnt
            else:
                summary["Unverified"] += cnt

        cursor.close()
        conn.close()
        return True, summary
    except Exception:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        return False, summary


def fetch_duplicate_summary():
    """
    Fetch summary counters for duplicate & related report status.
    """
    conn = None
    summary = {
        "Unique Reports": 0,
        "Related Reports": 0,
        "Potential Duplicates": 0
    }
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT COALESCE(duplicate_status, 'Unique') as status, COUNT(*) as count
            FROM weather_reports
            GROUP BY COALESCE(duplicate_status, 'Unique');
        """)
        rows = cursor.fetchall()

        for r in rows:
            st_key = r.get("status")
            cnt = r.get("count", 0)
            if st_key == "Unique":
                summary["Unique Reports"] = cnt
            elif st_key == "Related Report":
                summary["Related Reports"] = cnt
            elif st_key == "Potential Duplicate":
                summary["Potential Duplicates"] = cnt

        cursor.close()
        conn.close()
        return True, summary
    except Exception:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        return False, summary


def fetch_source_trust_summary():
    """
    Fetch summary statistics for Source Trust Scoring:
    - Average Trust Score
    - High Trust Sources Count
    - Medium Trust Sources Count
    - Low Trust Sources Count
    - Source Summary Table rows (Source, Count, Avg Score, Max Score, Min Score)
    """
    conn = None
    summary = {
        "avg_trust": 0.0,
        "high_trust_count": 0,
        "medium_trust_count": 0,
        "low_trust_count": 0,
        "source_rows": []
    }
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Average trust score across all reports
        cursor.execute("SELECT AVG(trust_score) as avg_trust FROM weather_reports WHERE trust_score IS NOT NULL;")
        avg_row = cursor.fetchone()
        if avg_row and avg_row["avg_trust"] is not None:
            summary["avg_trust"] = round(float(avg_row["avg_trust"]), 1)

        # High, Medium, Low counts
        cursor.execute("SELECT COUNT(*) as cnt FROM weather_reports WHERE trust_score >= 80.0;")
        summary["high_trust_count"] = cursor.fetchone()["cnt"]

        cursor.execute("SELECT COUNT(*) as cnt FROM weather_reports WHERE trust_score >= 50.0 AND trust_score < 80.0;")
        summary["medium_trust_count"] = cursor.fetchone()["cnt"]

        cursor.execute("SELECT COUNT(*) as cnt FROM weather_reports WHERE trust_score < 50.0 OR trust_score IS NULL;")
        summary["low_trust_count"] = cursor.fetchone()["cnt"]

        # Source Summary Table breakdown
        cursor.execute("""
            SELECT 
                COALESCE(source, 'Citizen Report') as source_name,
                COUNT(*) as count,
                AVG(trust_score) as avg_score,
                MAX(trust_score) as max_score,
                MIN(trust_score) as min_score
            FROM weather_reports
            GROUP BY COALESCE(source, 'Citizen Report')
            ORDER BY count DESC;
        """)
        summary["source_rows"] = cursor.fetchall()

        cursor.close()
        conn.close()
        return True, summary
    except Exception:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        return False, summary


def save_api_weather_data(weather_info):
    """
    Insert a record into api_weather_data table.
    """
    conn = None
    try:
        if "event_type" not in weather_info or not weather_info.get("event_type"):
            event_type, confidence, classified_at = WeatherEventClassifier.classify(
                temperature=weather_info.get("temperature"),
                humidity=weather_info.get("humidity"),
                wind_speed=weather_info.get("wind_speed"),
                weather_condition=weather_info.get("weather_condition"),
                weather_description=weather_info.get("weather_description")
            )
            weather_info["event_type"] = event_type
            weather_info["event_confidence"] = confidence
            weather_info["classified_at"] = classified_at

        conn = get_db_connection()
        cursor = conn.cursor()

        sql = """
        INSERT INTO api_weather_data (
            source,
            city,
            state,
            latitude,
            longitude,
            temperature,
            humidity,
            wind_speed,
            weather_condition,
            weather_description,
            recorded_at,
            event_type,
            event_confidence,
            classified_at
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        ) RETURNING id;
        """

        cursor.execute(sql, (
            weather_info.get("source", "OpenWeatherMap API"),
            weather_info.get("city"),
            weather_info.get("state", ""),
            weather_info.get("latitude"),
            weather_info.get("longitude"),
            weather_info.get("temperature"),
            weather_info.get("humidity"),
            weather_info.get("wind_speed"),
            weather_info.get("weather_condition"),
            weather_info.get("weather_description"),
            weather_info.get("recorded_at"),
            weather_info.get("event_type"),
            weather_info.get("event_confidence"),
            weather_info.get("classified_at")
        ))

        new_id = cursor.fetchone()[0]
        try:
            process_alert_for_observation(cursor, new_id, weather_info)
        except Exception as alert_err:
            print("Alert creation error during ingestion:", alert_err)
        conn.commit()
        cursor.close()
        conn.close()
        return True, new_id
    except Exception as e:
        if conn:
            try:
                conn.close()
            except Exception:
                pass

        error_msg = str(e)
        password = os.getenv("DB_PASSWORD") or os.getenv("POSTGRES_PASSWORD") or os.getenv("PGPASSWORD") or ""
        if password and password in error_msg:
            error_msg = error_msg.replace(password, "******")

        return False, error_msg


def fetch_recent_api_weather_data(limit=10):
    """
    Fetch recent API weather records from api_weather_data table.
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM api_weather_data ORDER BY created_at DESC LIMIT %s;", (limit,))
        records = cursor.fetchall()
        cursor.close()
        conn.close()
        return True, records
    except Exception as e:
        if conn:
            try:
                conn.close()
            except Exception:
                pass

        error_msg = str(e)
        password = os.getenv("DB_PASSWORD") or os.getenv("POSTGRES_PASSWORD") or os.getenv("PGPASSWORD") or ""
        if password and password in error_msg:
            error_msg = error_msg.replace(password, "******")

        return False, error_msg


def fetch_total_api_weather_count():
    """
    Fetch the total count of records in api_weather_data table.
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM api_weather_data;")
        row = cursor.fetchone()
        total = row[0] if row else 0
        cursor.close()
        conn.close()
        return True, total
    except Exception as e:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        return False, 0



def fetch_ai_event_summary():
    """
    Fetch summary counts of classified observations grouped by event_type from api_weather_data.
    """
    conn = None
    summary_counts = {
        "Total Observations": 0,
        "Normal Weather": 0,
        "Heavy Rainfall": 0,
        "Thunderstorm": 0,
        "Heatwave": 0,
        "Fog": 0,
        "Strong Wind": 0,
        "Dust Storm": 0,
        "Flood Risk": 0
    }
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT event_type, COUNT(*) as count 
            FROM api_weather_data 
            WHERE event_type IS NOT NULL 
            GROUP BY event_type;
        """)
        rows = cursor.fetchall()

        cursor.execute("SELECT COUNT(*) as total FROM api_weather_data;")
        total_row = cursor.fetchone()
        if total_row:
            summary_counts["Total Observations"] = total_row["total"]

        for row in rows:
            etype = row.get("event_type")
            count = row.get("count", 0)
            if etype in summary_counts:
                summary_counts[etype] = count

        cursor.close()
        conn.close()
        return True, summary_counts
    except Exception:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        return False, summary_counts


def fetch_classified_events(event_filter=None, limit=50):
    """
    Fetch classified weather observations from api_weather_data with optional event_type filtering.
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        if event_filter and event_filter.strip() and event_filter.strip() != "All":
            cursor.execute(
                "SELECT * FROM api_weather_data WHERE event_type = %s ORDER BY created_at DESC LIMIT %s;",
                (event_filter.strip(), limit)
            )
        else:
            cursor.execute(
                "SELECT * FROM api_weather_data ORDER BY created_at DESC LIMIT %s;",
                (limit,)
            )

        records = cursor.fetchall()
        cursor.close()
        conn.close()
        return True, records
    except Exception as e:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        error_msg = str(e)
        password = os.getenv("DB_PASSWORD") or os.getenv("POSTGRES_PASSWORD") or os.getenv("PGPASSWORD") or ""
        if password and password in error_msg:
            error_msg = error_msg.replace(password, "******")
        return False, error_msg


def classify_existing_unclassified_data():
    """
    Backfill classification for any existing api_weather_data rows where event_type IS NULL.
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM api_weather_data WHERE event_type IS NULL;")
        unclassified = cursor.fetchall()

        if unclassified:
            update_cursor = conn.cursor()
            for row in unclassified:
                etype, conf, cat = WeatherEventClassifier.classify(
                    temperature=row.get("temperature"),
                    humidity=row.get("humidity"),
                    wind_speed=row.get("wind_speed"),
                    weather_condition=row.get("weather_condition"),
                    weather_description=row.get("weather_description")
                )
                update_cursor.execute(
                    "UPDATE api_weather_data SET event_type = %s, event_confidence = %s, classified_at = %s WHERE id = %s;",
                    (etype, conf, cat, row["id"])
                )
            conn.commit()
            update_cursor.close()

        cursor.close()
        conn.close()
        return True, f"Classified {len(unclassified)} existing records."
    except Exception as e:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        return False, str(e)


def analyze_unanalyzed_weather_reports():
    """
    Automatically analyze any weather_reports rows where trust_score OR verification_result IS NULL.
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT id FROM weather_reports WHERE trust_score IS NULL OR verification_result IS NULL;")
        unanalyzed = cursor.fetchall()
        cursor.close()
        conn.close()

        if unanalyzed:
            for row in unanalyzed:
                analyze_and_update_report(row["id"])
            return True, f"Analyzed {len(unanalyzed)} weather reports."
        return True, "No unanalyzed weather reports found."
    except Exception as e:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        return False, str(e)


def fetch_map_geographic_records():
    """
    Fetch valid geographic records (latitude, longitude IS NOT NULL) from both api_weather_data and weather_reports tables
    for spatial weather map rendering.
    """
    conn = None
    map_records = []
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # 1. Fetch geographic records from api_weather_data
        cursor.execute("""
            SELECT 
                id,
                COALESCE(source, 'OpenWeatherMap API') as source,
                city,
                state,
                latitude,
                longitude,
                temperature,
                humidity,
                wind_speed,
                weather_condition,
                weather_description,
                COALESCE(event_type, 'Normal Weather') as event_type,
                event_confidence,
                recorded_at,
                created_at,
                'api_observation' as record_kind
            FROM api_weather_data
            WHERE latitude IS NOT NULL AND longitude IS NOT NULL AND latitude != 0 AND longitude != 0;
        """)
        api_rows = cursor.fetchall()
        for r in api_rows:
            r["latitude"] = float(r["latitude"])
            r["longitude"] = float(r["longitude"])
            if r.get("temperature") is not None:
                r["temperature"] = float(r["temperature"])
            if r.get("humidity") is not None:
                r["humidity"] = float(r["humidity"])
            if r.get("wind_speed") is not None:
                r["wind_speed"] = float(r["wind_speed"])
            map_records.append(r)

        # 2. Fetch geographic records from weather_reports
        cursor.execute("""
            SELECT 
                id,
                COALESCE(source, 'Citizen Report') as source,
                source_url,
                report_text,
                COALESCE(event_type, 'Normal Weather') as event_type,
                report_datetime,
                city,
                state,
                latitude,
                longitude,
                image_url,
                video_url,
                COALESCE(verification_result, verification_status, 'Unverified') as verification_result,
                verification_score,
                duplicate_status,
                trust_score,
                trust_reason,
                created_at,
                'citizen_report' as record_kind
            FROM weather_reports
            WHERE latitude IS NOT NULL AND longitude IS NOT NULL AND latitude != 0 AND longitude != 0;
        """)
        report_rows = cursor.fetchall()
        for r in report_rows:
            r["latitude"] = float(r["latitude"])
            r["longitude"] = float(r["longitude"])
            if r.get("trust_score") is not None:
                r["trust_score"] = float(r["trust_score"])
            if r.get("verification_score") is not None:
                r["verification_score"] = float(r["verification_score"])
            map_records.append(r)

        cursor.close()
        conn.close()
        return True, map_records
    except Exception as e:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        return False, str(e)


def fetch_advanced_analytics(start_date=None, end_date=None, event_type=None, state=None, source=None):
    """
    Fetch comprehensive aggregated analytics from PostgreSQL database tables (weather_reports, api_weather_data, and weather_alerts)
    with support for safe parameterized filtering by date range, event_type, state, and source.
    """
    conn = None
    analytics = {
        "overall_summary": {
            "total_reports": 0,
            "total_weather_observations": 0,
            "verified_reports": 0,
            "suspicious_reports": 0,
            "needs_verification": 0,
            "total_active_event_types": 0,
            "total_states": 0,
            "average_trust_score": 0.0
        },
        "events_by_type": [],
        "events_by_state": [],
        "reports_over_time": [],
        "source_distribution": [],
        "verification_distribution": [],
        "trust_score_distribution": [],
        "top_cities": [],
        "top_sources": []
    }
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Build parameterized WHERE conditions for weather_reports
        wr_conds = ["1=1"]
        wr_params = []
        if start_date and start_date.strip():
            wr_conds.append("created_at >= %s")
            wr_params.append(start_date.strip() + " 00:00:00")
        if end_date and end_date.strip():
            wr_conds.append("created_at <= %s")
            wr_params.append(end_date.strip() + " 23:59:59")
        if event_type and event_type.strip() and event_type.strip() != "All":
            wr_conds.append("event_type = %s")
            wr_params.append(event_type.strip())
        if state and state.strip() and state.strip() != "All":
            wr_conds.append("state = %s")
            wr_params.append(state.strip())
        if source and source.strip() and source.strip() != "All":
            wr_conds.append("(source = %s OR source ILIKE %s)")
            wr_params.extend([source.strip(), f"%{source.strip()}%"])

        wr_where = " AND ".join(wr_conds)

        # Build parameterized WHERE conditions for api_weather_data
        api_conds = ["1=1"]
        api_params = []
        if start_date and start_date.strip():
            api_conds.append("created_at >= %s")
            api_params.append(start_date.strip() + " 00:00:00")
        if end_date and end_date.strip():
            api_conds.append("created_at <= %s")
            api_params.append(end_date.strip() + " 23:59:59")
        if event_type and event_type.strip() and event_type.strip() != "All":
            api_conds.append("event_type = %s")
            api_params.append(event_type.strip())
        if state and state.strip() and state.strip() != "All":
            api_conds.append("state = %s")
            api_params.append(state.strip())
        if source and source.strip() and source.strip() != "All":
            api_conds.append("(source = %s OR source ILIKE %s)")
            api_params.extend([source.strip(), f"%{source.strip()}%"])

        api_where = " AND ".join(api_conds)

        # Build parameterized WHERE conditions for weather_alerts
        wa_conds = ["1=1"]
        wa_params = []
        if start_date and start_date.strip():
            wa_conds.append("created_at >= %s")
            wa_params.append(start_date.strip() + " 00:00:00")
        if end_date and end_date.strip():
            wa_conds.append("created_at <= %s")
            wa_params.append(end_date.strip() + " 23:59:59")
        if event_type and event_type.strip() and event_type.strip() != "All":
            wa_conds.append("event_type = %s")
            wa_params.append(event_type.strip())
        if state and state.strip() and state.strip() != "All":
            wa_conds.append("state = %s")
            wa_params.append(state.strip())
        if source and source.strip() and source.strip() != "All":
            wa_conds.append("(source = %s OR source ILIKE %s)")
            wa_params.extend([source.strip(), f"%{source.strip()}%"])

        wa_where = " AND ".join(wa_conds)

        # 1. Total Citizen / Multi-Source Reports
        cursor.execute(f"SELECT COUNT(*) as total FROM weather_reports WHERE {wr_where};", tuple(wr_params))
        row = cursor.fetchone()
        if row:
            analytics["overall_summary"]["total_reports"] = int(row["total"])

        # 2. Total Weather Observations (API Ingestion)
        cursor.execute(f"SELECT COUNT(*) as total FROM api_weather_data WHERE {api_where};", tuple(api_params))
        row = cursor.fetchone()
        if row:
            analytics["overall_summary"]["total_weather_observations"] = int(row["total"])

        # 3. Verified Reports (Likely Consistent / Verified)
        cursor.execute(f"SELECT COUNT(*) as cnt FROM weather_reports WHERE {wr_where} AND (verification_result IN ('Likely Consistent', 'Verified') OR verification_status IN ('Likely Consistent', 'Verified'));", tuple(wr_params))
        row = cursor.fetchone()
        if row:
            analytics["overall_summary"]["verified_reports"] = int(row["cnt"])

        # 4. Suspicious Reports
        cursor.execute(f"SELECT COUNT(*) as cnt FROM weather_reports WHERE {wr_where} AND (verification_result = 'Suspicious' OR verification_status = 'Suspicious');", tuple(wr_params))
        row = cursor.fetchone()
        if row:
            analytics["overall_summary"]["suspicious_reports"] = int(row["cnt"])

        # 5. Needs Verification Reports
        cursor.execute(f"SELECT COUNT(*) as cnt FROM weather_reports WHERE {wr_where} AND (verification_result = 'Needs Verification' OR verification_status = 'Needs Verification' OR (verification_result IS NULL AND verification_status IS NULL));", tuple(wr_params))
        row = cursor.fetchone()
        if row:
            analytics["overall_summary"]["needs_verification"] = int(row["cnt"])

        # 6. Total Active Event Types
        cursor.execute(f"SELECT COUNT(DISTINCT event_type) as cnt FROM (SELECT event_type FROM weather_reports WHERE {wr_where} AND event_type IS NOT NULL AND event_type != '' UNION SELECT event_type FROM api_weather_data WHERE {api_where} AND event_type IS NOT NULL AND event_type != '' UNION SELECT event_type FROM weather_alerts WHERE {wa_where} AND event_type IS NOT NULL AND event_type != '') t;", tuple(wr_params + api_params + wa_params))
        row = cursor.fetchone()
        if row:
            analytics["overall_summary"]["total_active_event_types"] = int(row["cnt"])

        # 7. Total States Covered
        cursor.execute(f"SELECT COUNT(DISTINCT state) as cnt FROM (SELECT state FROM weather_reports WHERE {wr_where} AND state IS NOT NULL AND state != '' UNION SELECT state FROM api_weather_data WHERE {api_where} AND state IS NOT NULL AND state != '' UNION SELECT state FROM weather_alerts WHERE {wa_where} AND state IS NOT NULL AND state != '') t;", tuple(wr_params + api_params + wa_params))
        row = cursor.fetchone()
        if row:
            analytics["overall_summary"]["total_states"] = int(row["cnt"])

        # 8. Average Trust Score
        cursor.execute(f"SELECT AVG(trust_score) as avg_score FROM weather_reports WHERE {wr_where} AND trust_score IS NOT NULL;", tuple(wr_params))
        row = cursor.fetchone()
        if row and row["avg_score"] is not None:
            analytics["overall_summary"]["average_trust_score"] = round(float(row["avg_score"]), 1)

        # Chart 1: Weather Events by Type
        cursor.execute(f"""
            SELECT 
                CASE 
                    WHEN LOWER(event_type) IN ('flooding', 'flood risk', 'flood') THEN 'Flood Risk'
                    WHEN LOWER(event_type) IN ('rainfall', 'heavy rainfall', 'heavy rain') THEN 'Heavy Rainfall'
                    WHEN LOWER(event_type) IN ('thunderstorm', 'lightning') THEN 'Thunderstorm'
                    WHEN LOWER(event_type) IN ('heatwave', 'extreme heat') THEN 'Heatwave'
                    WHEN LOWER(event_type) IN ('fog', 'mist', 'fog / mist', 'fog / low visibility') THEN 'Fog / Mist'
                    WHEN LOWER(event_type) IN ('dust storm', 'duststorm') THEN 'Dust Storm'
                    WHEN LOWER(event_type) IN ('strong wind', 'strong winds', 'high winds') THEN 'Strong Winds'
                    WHEN LOWER(event_type) IN ('normal weather', 'clear', 'normal') THEN 'Normal Weather'
                    ELSE INITCAP(event_type)
                END as event_type,
                COUNT(*)::int as count 
            FROM (
                SELECT event_type FROM weather_reports WHERE {wr_where} AND event_type IS NOT NULL AND event_type != ''
                UNION ALL 
                SELECT event_type FROM api_weather_data WHERE {api_where} AND event_type IS NOT NULL AND event_type != ''
                UNION ALL
                SELECT event_type FROM weather_alerts WHERE {wa_where} AND event_type IS NOT NULL AND event_type != ''
            ) t 
            GROUP BY 1 
            ORDER BY count DESC;
        """, tuple(wr_params + api_params + wa_params))
        analytics["events_by_type"] = cursor.fetchall()

        # Chart 2: Weather Events by State
        cursor.execute(f"""
            SELECT state, COUNT(*)::int as count 
            FROM (
                SELECT state FROM weather_reports WHERE {wr_where} AND state IS NOT NULL AND state != '' 
                UNION ALL 
                SELECT state FROM api_weather_data WHERE {api_where} AND state IS NOT NULL AND state != ''
                UNION ALL
                SELECT state FROM weather_alerts WHERE {wa_where} AND state IS NOT NULL AND state != ''
            ) t 
            GROUP BY state 
            ORDER BY count DESC 
            LIMIT 15;
        """, tuple(wr_params + api_params + wa_params))
        analytics["events_by_state"] = cursor.fetchall()

        # Chart 3: Reports Over Time
        cursor.execute(f"""
            SELECT TO_CHAR(DATE(created_at), 'YYYY-MM-DD') as date, COUNT(*)::int as count 
            FROM (
                SELECT created_at FROM weather_reports WHERE {wr_where} AND created_at IS NOT NULL
                UNION ALL
                SELECT created_at FROM api_weather_data WHERE {api_where} AND created_at IS NOT NULL
                UNION ALL
                SELECT created_at FROM weather_alerts WHERE {wa_where} AND created_at IS NOT NULL
            ) t
            GROUP BY DATE(created_at) 
            ORDER BY date ASC;
        """, tuple(wr_params + api_params + wa_params))
        analytics["reports_over_time"] = cursor.fetchall()

        # Chart 4: Reports by Source
        cursor.execute(f"""
            SELECT source, COUNT(*)::int as count 
            FROM (
                SELECT COALESCE(source, 'Citizen Report') as source FROM weather_reports WHERE {wr_where}
                UNION ALL
                SELECT COALESCE(source, 'OpenWeatherMap API') as source FROM api_weather_data WHERE {api_where}
                UNION ALL
                SELECT COALESCE(source, 'SACHET / NDMA') as source FROM weather_alerts WHERE {wa_where}
            ) t
            GROUP BY source 
            ORDER BY count DESC;
        """, tuple(wr_params + api_params + wa_params))
        analytics["source_distribution"] = cursor.fetchall()

        # Chart 5: Verification Status Distribution
        cursor.execute(f"""
            SELECT COALESCE(verification_result, verification_status, 'Unverified') as status, COUNT(*)::int as count 
            FROM weather_reports 
            WHERE {wr_where} 
            GROUP BY COALESCE(verification_result, verification_status, 'Unverified') 
            ORDER BY count DESC;
        """, tuple(wr_params))
        analytics["verification_distribution"] = cursor.fetchall()

        # Chart 6: Trust Score Distribution
        cursor.execute(f"""
            SELECT 
                COUNT(CASE WHEN trust_score >= 80.0 THEN 1 END)::int as high_trust,
                COUNT(CASE WHEN trust_score >= 50.0 AND trust_score < 80.0 THEN 1 END)::int as medium_trust,
                COUNT(CASE WHEN trust_score < 50.0 OR trust_score IS NULL THEN 1 END)::int as low_trust
            FROM weather_reports 
            WHERE {wr_where};
        """, tuple(wr_params))
        t_row = cursor.fetchone()
        if t_row:
            analytics["trust_score_distribution"] = [
                {"label": "High Trust (80-100)", "count": int(t_row["high_trust"])},
                {"label": "Medium Trust (50-79)", "count": int(t_row["medium_trust"])},
                {"label": "Low Trust (0-49)", "count": int(t_row["low_trust"])}
            ]

        # Chart 7: Top 10 Affected Cities
        cursor.execute(f"""
            SELECT city, MAX(state) as state, COUNT(*)::int as count 
            FROM (
                SELECT city, state FROM weather_reports WHERE {wr_where} AND city IS NOT NULL AND city != '' 
                UNION ALL 
                SELECT city, state FROM api_weather_data WHERE {api_where} AND city IS NOT NULL AND city != ''
                UNION ALL
                SELECT city, state FROM weather_alerts WHERE {wa_where} AND city IS NOT NULL AND city != ''
            ) t 
            GROUP BY city 
            ORDER BY count DESC 
            LIMIT 10;
        """, tuple(wr_params + api_params + wa_params))
        analytics["top_cities"] = cursor.fetchall()

        # Chart 8: Top Sources by Average Trust
        cursor.execute(f"""
            SELECT 
                source, 
                COUNT(*)::int as count, 
                ROUND(AVG(trust_score)::numeric, 1)::float as avg_trust 
            FROM (
                SELECT COALESCE(source, 'Citizen Report') as source, COALESCE(trust_score, 70.0) as trust_score FROM weather_reports WHERE {wr_where}
                UNION ALL
                SELECT COALESCE(source, 'OpenWeatherMap API') as source, 90.0 as trust_score FROM api_weather_data WHERE {api_where}
                UNION ALL
                SELECT COALESCE(source, 'SACHET / NDMA') as source, 95.0 as trust_score FROM weather_alerts WHERE {wa_where}
            ) t
            GROUP BY source 
            ORDER BY avg_trust DESC;
        """, tuple(wr_params + api_params + wa_params))
        analytics["top_sources"] = cursor.fetchall()

        cursor.close()
        conn.close()
        return True, analytics
    except Exception as e:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        return False, str(e)


def process_alert_for_observation(cursor, obs_id, weather_info):
    """
    Check if a weather observation indicates a significant non-normal weather event,
    and create a weather alert if deduplication rules pass (no active alert for same city and event in last 6 hrs).
    """
    try:
        event_type = weather_info.get("event_type")
        if not event_type or event_type in ["Normal Weather", "Clear Sky"]:
            return None

        confidence = float(weather_info.get("event_confidence") or 0.0)
        city = weather_info.get("city")
        if not city:
            return None

        high_events = ["Flood Risk", "Heavy Rainfall", "Heatwave", "Dust Storm"]
        medium_events = ["Thunderstorm", "Strong Wind", "Flood Risk", "Heavy Rainfall"]

        if event_type in high_events and confidence >= 75.0:
            severity = "HIGH"
        elif confidence >= 60.0 or event_type in medium_events:
            severity = "MEDIUM"
        else:
            severity = "LOW"

        # Deduplication: check active alert for same city and event_type in last 6 hours
        cursor.execute("""
            SELECT id FROM weather_alerts
            WHERE LOWER(city) = LOWER(%s)
              AND event_type = %s
              AND status = 'Active'
              AND detected_at >= NOW() - INTERVAL '6 hours';
        """, (city.strip(), event_type))

        existing = cursor.fetchone()
        if existing:
            return None

        cursor.execute("""
            INSERT INTO weather_alerts (
                weather_observation_id, event_type, severity, city, state,
                latitude, longitude, event_confidence, status, detected_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, 'Active', CURRENT_TIMESTAMP
            ) RETURNING id, weather_observation_id, event_type, severity, city, state, latitude, longitude, event_confidence, status, detected_at;
        """, (
            obs_id,
            event_type,
            severity,
            city.strip(),
            weather_info.get("state", ""),
            weather_info.get("latitude"),
            weather_info.get("longitude"),
            confidence
        ))

        row = cursor.fetchone()
        alert_dict = {
            "id": row[0],
            "weather_observation_id": row[1],
            "event_type": row[2],
            "severity": row[3],
            "city": row[4],
            "state": row[5],
            "latitude": row[6],
            "longitude": row[7],
            "event_confidence": float(row[8]) if row[8] is not None else 0.0,
            "status": row[9],
            "detected_at": str(row[10]) if row[10] else None
        }

        try:
            from socketio_instance import broadcast_weather_alert
            broadcast_weather_alert(alert_dict)
        except Exception as e:
            print("Alert SocketIO broadcast error:", e)

        return alert_dict
    except Exception as err:
        print("Error processing alert for observation:", err)
        return None


def insert_sachet_alerts_to_db(alerts_list):
    """
    Insert a list of parsed SACHET/NDMA RSS disaster alert dictionaries into PostgreSQL weather_alerts table.
    Guarantees duplicate protection by checking guid and link.
    Returns tuple: (imported_count, skipped_count)
    """
    if not alerts_list:
        return 0, 0

    init_db()
    conn = None
    imported_count = 0
    skipped_count = 0

    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        for a in alerts_list:
            guid = a.get("guid")
            link = a.get("link")

            # Check if this exact SACHET alert already exists in weather_alerts table
            if guid:
                cursor.execute("SELECT id FROM weather_alerts WHERE guid = %s;", (guid,))
            elif link:
                cursor.execute("SELECT id FROM weather_alerts WHERE link = %s;", (link,))
            else:
                cursor.execute("""
                    SELECT id FROM weather_alerts 
                    WHERE source = 'SACHET / NDMA' 
                      AND event_type = %s 
                      AND LOWER(city) = LOWER(%s) 
                      AND detected_at = %s;
                """, (a.get("event_type"), a.get("city"), a.get("detected_at")))

            existing = cursor.fetchone()
            if existing:
                skipped_count += 1
                continue

            # Insert new SACHET disaster alert into PostgreSQL weather_alerts table
            insert_sql = """
                INSERT INTO weather_alerts (
                    source, title, description, link, guid, instruction, publisher,
                    event_type, severity, city, state, latitude, longitude,
                    event_confidence, status, detected_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s
                ) RETURNING id, source, title, description, event_type, severity, city, state, latitude, longitude, status, detected_at;
            """
            cursor.execute(insert_sql, (
                a.get("source", "SACHET / NDMA"),
                a.get("title"),
                a.get("description"),
                a.get("link"),
                guid,
                a.get("instruction"),
                a.get("publisher"),
                a.get("event_type"),
                a.get("severity"),
                a.get("city"),
                a.get("state"),
                a.get("latitude"),
                a.get("longitude"),
                a.get("event_confidence", 95.0),
                a.get("status", "Active"),
                a.get("detected_at")
            ))
            row = cursor.fetchone()
            conn.commit()
            imported_count += 1

            # Broadcast real-time SocketIO event for new alert
            try:
                from socketio_instance import broadcast_weather_alert
                alert_payload = {
                    "id": row["id"],
                    "source": row["source"],
                    "title": row["title"],
                    "event_type": row["event_type"],
                    "severity": row["severity"],
                    "city": row["city"],
                    "state": row["state"],
                    "latitude": row["latitude"],
                    "longitude": row["longitude"],
                    "status": row["status"],
                    "detected_at": str(row["detected_at"]) if row["detected_at"] else ""
                }
                broadcast_weather_alert(alert_payload)
            except Exception:
                pass

        cursor.close()
        conn.close()
        return imported_count, skipped_count

    except Exception as e:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        raise e


def fetch_national_alerts(event_type=None, severity=None, status=None, state=None, city=None, page=1, per_page=20):
    """
    Fetch weather alerts with multi-criteria filtering, summary metrics, analytics breakdowns, and pagination.
    Queries real PostgreSQL weather_alerts database records.
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        where_clauses = []
        params = []

        if event_type and event_type.strip() and event_type.lower() != 'all':
            where_clauses.append("a.event_type = %s")
            params.append(event_type.strip())

        if severity and severity.strip() and severity.lower() != 'all':
            where_clauses.append("a.severity = %s")
            params.append(severity.strip().upper())

        if status and status.strip() and status.lower() != 'all':
            where_clauses.append("a.status = %s")
            params.append(status.strip().capitalize())

        if state and state.strip() and state.lower() != 'all':
            where_clauses.append("a.state = %s")
            params.append(state.strip())

        if city and city.strip():
            where_clauses.append("LOWER(a.city) LIKE LOWER(%s)")
            params.append(f"%{city.strip()}%")

        where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

        cursor.execute(f"SELECT COUNT(*) as cnt FROM weather_alerts a {where_sql};", tuple(params))
        total_count = cursor.fetchone()["cnt"]

        try:
            page = max(1, int(page))
        except (ValueError, TypeError):
            page = 1

        try:
            per_page = max(1, min(100, int(per_page)))
        except (ValueError, TypeError):
            per_page = 20

        total_pages = max(1, math.ceil(total_count / per_page))
        offset = (page - 1) * per_page

        query = f"""
            SELECT 
                a.id,
                a.weather_observation_id,
                a.event_type,
                a.severity,
                a.city,
                a.state,
                a.latitude,
                a.longitude,
                a.event_confidence,
                a.status,
                COALESCE(a.source, 'Automated System') as source,
                COALESCE(a.title, a.event_type || ' Alert - ' || a.city) as title,
                a.description,
                a.link,
                a.guid,
                a.instruction,
                a.publisher,
                a.detected_at,
                a.resolved_at,
                a.created_at,
                o.temperature,
                o.humidity,
                o.wind_speed,
                o.weather_condition,
                o.weather_description
            FROM weather_alerts a
            LEFT JOIN api_weather_data o ON a.weather_observation_id = o.id
            {where_sql}
            ORDER BY a.detected_at DESC
            LIMIT %s OFFSET %s;
        """
        cursor.execute(query, tuple(params + [per_page, offset]))
        raw_alerts = cursor.fetchall()

        alerts = []
        for row in raw_alerts:
            alerts.append({
                "id": row["id"],
                "weather_observation_id": row["weather_observation_id"],
                "event_type": row["event_type"],
                "severity": row["severity"],
                "city": row["city"],
                "state": row["state"] or "",
                "latitude": float(row["latitude"]) if row["latitude"] is not None else None,
                "longitude": float(row["longitude"]) if row["longitude"] is not None else None,
                "event_confidence": float(row["event_confidence"]) if row["event_confidence"] is not None else 0.0,
                "status": row["status"],
                "source": row["source"],
                "title": row["title"],
                "description": row["description"] or row["weather_description"] or "",
                "link": row["link"] or "",
                "guid": row["guid"] or "",
                "instruction": row["instruction"] or "",
                "publisher": row["publisher"] or "",
                "detected_at": row["detected_at"].strftime("%Y-%m-%d %H:%M:%S") if row["detected_at"] else "",
                "resolved_at": row["resolved_at"].strftime("%Y-%m-%d %H:%M:%S") if row["resolved_at"] else None,
                "temperature": float(row["temperature"]) if row["temperature"] is not None else None,
                "humidity": float(row["humidity"]) if row["humidity"] is not None else None,
                "wind_speed": float(row["wind_speed"]) if row["wind_speed"] is not None else None,
                "weather_condition": row["weather_condition"] or "",
                "weather_description": row["weather_description"] or ""
            })

        # Real PostgreSQL Database Summary Metrics
        cursor.execute("SELECT COUNT(*) as cnt FROM weather_alerts WHERE status = 'Active';")
        total_active = cursor.fetchone()["cnt"]

        cursor.execute("SELECT COUNT(*) as cnt FROM weather_alerts WHERE status = 'Resolved';")
        total_resolved = cursor.fetchone()["cnt"]

        cursor.execute("SELECT COUNT(*) as cnt FROM weather_alerts WHERE status = 'Active' AND severity = 'HIGH';")
        high_severity = cursor.fetchone()["cnt"]

        cursor.execute("SELECT COUNT(*) as cnt FROM weather_alerts WHERE status = 'Active' AND severity = 'MEDIUM';")
        medium_severity = cursor.fetchone()["cnt"]

        cursor.execute("SELECT COUNT(*) as cnt FROM weather_alerts WHERE status = 'Active' AND severity = 'LOW';")
        low_severity = cursor.fetchone()["cnt"]

        cursor.execute("SELECT COUNT(DISTINCT event_type) as cnt FROM weather_alerts WHERE status = 'Active';")
        active_event_types = cursor.fetchone()["cnt"]

        summary = {
            "total_active": total_active,
            "total_resolved": total_resolved,
            "high_severity": high_severity,
            "medium_severity": medium_severity,
            "low_severity": low_severity,
            "active_event_types": active_event_types
        }

        # Real PostgreSQL Database Analytics Breakdowns
        cursor.execute("""
            SELECT severity, COUNT(*) as count 
            FROM weather_alerts 
            GROUP BY severity 
            ORDER BY count DESC;
        """)
        severity_dist = cursor.fetchall()

        cursor.execute("""
            SELECT event_type, COUNT(*) as count 
            FROM weather_alerts 
            GROUP BY event_type 
            ORDER BY count DESC 
            LIMIT 10;
        """)
        event_dist = cursor.fetchall()

        cursor.execute("""
            SELECT COALESCE(state, 'Unknown') as state, COUNT(*) as count 
            FROM weather_alerts 
            WHERE state IS NOT NULL AND state != '' 
            GROUP BY COALESCE(state, 'Unknown') 
            ORDER BY count DESC 
            LIMIT 10;
        """)
        state_dist = cursor.fetchall()

        analytics = {
            "severity_distribution": severity_dist,
            "event_distribution": event_dist,
            "state_distribution": state_dist
        }

        # Real PostgreSQL Database Timeline
        cursor.execute("""
            SELECT 
                a.id, a.event_type, a.severity, a.city, a.state, a.status, a.detected_at, o.temperature, COALESCE(a.source, 'Automated System') as source
            FROM weather_alerts a
            LEFT JOIN api_weather_data o ON a.weather_observation_id = o.id
            ORDER BY a.detected_at DESC
            LIMIT 10;
        """)
        raw_timeline = cursor.fetchall()
        timeline = []
        for t in raw_timeline:
            timeline.append({
                "id": t["id"],
                "event_type": t["event_type"],
                "severity": t["severity"],
                "city": t["city"],
                "state": t["state"] or "",
                "status": t["status"],
                "source": t["source"],
                "detected_at": t["detected_at"].strftime("%Y-%m-%d %H:%M") if t["detected_at"] else "",
                "temperature": float(t["temperature"]) if t["temperature"] is not None else None
            })

        cursor.close()
        conn.close()

        result = {
            "alerts": alerts,
            "summary": summary,
            "pagination": {
                "total_count": total_count,
                "total_pages": total_pages,
                "current_page": page,
                "per_page": per_page
            },
            "analytics": analytics,
            "timeline": timeline
        }
        return True, result

    except Exception as e:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        return False, str(e)


def fetch_alert_details(alert_id):
    """
    Fetch details of a single weather alert by ID, including joined observation metrics and matching citizen reports.
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute("""
            SELECT 
                a.id, a.weather_observation_id, a.event_type, a.severity, a.city, a.state,
                a.latitude, a.longitude, a.event_confidence, a.status, a.source, a.title, a.description,
                a.link, a.guid, a.instruction, a.publisher, a.detected_at, a.resolved_at, a.created_at,
                o.temperature, o.humidity, o.wind_speed, o.weather_condition, o.weather_description, o.source as observation_source, o.recorded_at
            FROM weather_alerts a
            LEFT JOIN api_weather_data o ON a.weather_observation_id = o.id
            WHERE a.id = %s;
        """, (alert_id,))
        alert_row = cursor.fetchone()

        if not alert_row:
            cursor.close()
            conn.close()
            return False, "Alert not found."

        alert_data = {
            "id": alert_row["id"],
            "weather_observation_id": alert_row["weather_observation_id"],
            "event_type": alert_row["event_type"],
            "severity": alert_row["severity"],
            "city": alert_row["city"],
            "state": alert_row["state"] or "",
            "latitude": float(alert_row["latitude"]) if alert_row["latitude"] is not None else None,
            "longitude": float(alert_row["longitude"]) if alert_row["longitude"] is not None else None,
            "event_confidence": float(alert_row["event_confidence"]) if alert_row["event_confidence"] is not None else 0.0,
            "status": alert_row["status"],
            "source": alert_row["source"] or "Automated System",
            "title": alert_row["title"] or f"{alert_row['event_type']} Alert",
            "description": alert_row["description"] or alert_row["weather_description"] or "",
            "link": alert_row["link"] or "",
            "instruction": alert_row["instruction"] or "",
            "publisher": alert_row["publisher"] or "",
            "detected_at": alert_row["detected_at"].strftime("%Y-%m-%d %H:%M:%S") if alert_row["detected_at"] else "",
            "resolved_at": alert_row["resolved_at"].strftime("%Y-%m-%d %H:%M:%S") if alert_row["resolved_at"] else None,
            "temperature": float(alert_row["temperature"]) if alert_row["temperature"] is not None else None,
            "humidity": float(alert_row["humidity"]) if alert_row["humidity"] is not None else None,
            "wind_speed": float(alert_row["wind_speed"]) if alert_row["wind_speed"] is not None else None,
            "weather_condition": alert_row["weather_condition"] or "",
            "weather_description": alert_row["weather_description"] or "",
            "observation_source": alert_row["observation_source"] or "Official API",
            "recorded_at": alert_row["recorded_at"].strftime("%Y-%m-%d %H:%M:%S") if alert_row["recorded_at"] else ""
        }

        cursor.execute("""
            SELECT id, source, report_text, event_type, report_datetime, city, state, verification_result, trust_score
            FROM weather_reports
            WHERE LOWER(city) = LOWER(%s)
            ORDER BY report_datetime DESC
            LIMIT 10;
        """, (alert_row["city"],))
        raw_reports = cursor.fetchall()
        related_reports = []
        for r in raw_reports:
            related_reports.append({
                "id": r["id"],
                "source": r["source"] or "Citizen Report",
                "report_text": r["report_text"],
                "event_type": r["event_type"],
                "report_datetime": r["report_datetime"].strftime("%Y-%m-%d %H:%M:%S") if r["report_datetime"] else "",
                "city": r["city"],
                "state": r["state"] or "",
                "verification_result": r["verification_result"] or "Unverified",
                "trust_score": float(r["trust_score"]) if r["trust_score"] is not None else None
            })

        cursor.close()
        conn.close()

        return True, {
            "alert": alert_data,
            "related_reports": related_reports
        }
    except Exception as e:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        return False, str(e)


def resolve_weather_alert(alert_id, resolved_by="Admin"):
    """
    Mark an active weather alert as 'Resolved' and set resolved_at timestamp.
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE weather_alerts
            SET status = 'Resolved', resolved_at = CURRENT_TIMESTAMP
            WHERE id = %s AND status = 'Active'
            RETURNING id;
        """, (alert_id,))
        updated = cursor.fetchone()
        conn.commit()
        cursor.close()
        conn.close()

        if updated:
            return True, f"Weather Alert #{alert_id} resolved successfully."
        else:
            return False, f"Alert #{alert_id} not found or is already resolved."
    except Exception as e:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        return False, str(e)


def build_report_export_filter(start_date=None, end_date=None, event_type=None, state=None, city=None, source=None, verification_status=None, trust_level=None):
    """
    Build parameterized WHERE conditions for weather_reports export filtering.
    """
    where_clauses = ["1=1"]
    params = []

    if start_date and start_date.strip():
        where_clauses.append("report_datetime >= %s")
        params.append(start_date.strip() + " 00:00:00")

    if end_date and end_date.strip():
        where_clauses.append("report_datetime <= %s")
        params.append(end_date.strip() + " 23:59:59")

    if event_type and event_type.strip() and event_type.strip().lower() != 'all':
        where_clauses.append("event_type = %s")
        params.append(event_type.strip())

    if state and state.strip() and state.strip().lower() != 'all':
        where_clauses.append("state = %s")
        params.append(state.strip())

    if city and city.strip():
        where_clauses.append("LOWER(city) LIKE LOWER(%s)")
        params.append(f"%{city.strip()}%")

    if source and source.strip() and source.strip().lower() != 'all':
        where_clauses.append("(source = %s OR source ILIKE %s)")
        params.extend([source.strip(), f"%{source.strip()}%"])

    if verification_status and verification_status.strip() and verification_status.strip().lower() != 'all':
        where_clauses.append("(verification_result = %s OR verification_status = %s)")
        params.extend([verification_status.strip(), verification_status.strip()])

    if trust_level and trust_level.strip() and trust_level.strip().lower() != 'all':
        lvl = trust_level.strip().lower()
        if lvl == 'high':
            where_clauses.append("trust_score >= 80.0")
        elif lvl == 'medium':
            where_clauses.append("trust_score >= 50.0 AND trust_score < 80.0")
        elif lvl == 'low':
            where_clauses.append("(trust_score < 50.0 OR trust_score IS NULL)")

    return " AND ".join(where_clauses), params


def fetch_export_summary_metrics(start_date=None, end_date=None, event_type=None, state=None, city=None, source=None, verification_status=None, trust_level=None):
    """
    Fetch live export summary statistics matching current filter criteria.
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        where_sql, params = build_report_export_filter(
            start_date, end_date, event_type, state, city, source, verification_status, trust_level
        )

        cursor.execute(f"SELECT COUNT(*) as total_reports FROM weather_reports WHERE {where_sql};", tuple(params))
        total_reports = cursor.fetchone()["total_reports"]

        cursor.execute(f"SELECT MIN(report_datetime) as min_date, MAX(report_datetime) as max_date FROM weather_reports WHERE {where_sql};", tuple(params))
        dates_row = cursor.fetchone()
        min_d = dates_row["min_date"].strftime("%Y-%m-%d") if dates_row and dates_row["min_date"] else "N/A"
        max_d = dates_row["max_date"].strftime("%Y-%m-%d") if dates_row and dates_row["max_date"] else "N/A"
        date_range_str = f"{min_d} to {max_d}" if min_d != "N/A" else "No matching records"

        cursor.execute(f"SELECT COUNT(DISTINCT event_type) as cnt FROM weather_reports WHERE {where_sql} AND event_type IS NOT NULL;", tuple(params))
        events_count = cursor.fetchone()["cnt"]

        cursor.execute(f"SELECT COUNT(DISTINCT state) as cnt FROM weather_reports WHERE {where_sql} AND state IS NOT NULL AND state != '';", tuple(params))
        states_count = cursor.fetchone()["cnt"]

        cursor.execute(f"SELECT AVG(trust_score) as avg_trust FROM weather_reports WHERE {where_sql} AND trust_score IS NOT NULL;", tuple(params))
        trust_row = cursor.fetchone()
        avg_trust = round(float(trust_row["avg_trust"]), 1) if trust_row and trust_row["avg_trust"] is not None else 0.0

        cursor.execute("SELECT COUNT(*) as cnt FROM api_weather_data;")
        total_obs = cursor.fetchone()["cnt"]

        cursor.execute("SELECT COUNT(*) as cnt FROM weather_alerts WHERE status = 'Active';")
        active_alerts = cursor.fetchone()["cnt"]

        cursor.close()
        conn.close()

        return True, {
            "total_reports": total_reports,
            "date_range": date_range_str,
            "events_count": events_count,
            "states_count": states_count,
            "average_trust": avg_trust,
            "total_observations": total_obs,
            "active_alerts": active_alerts
        }

    except Exception as e:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        return False, str(e)


def fetch_filtered_reports_for_export(start_date=None, end_date=None, event_type=None, state=None, city=None, source=None, verification_status=None, trust_level=None):
    """
    Fetch filtered weather report records from weather_reports table for CSV/JSON export.
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        where_sql, params = build_report_export_filter(
            start_date, end_date, event_type, state, city, source, verification_status, trust_level
        )

        query = f"""
            SELECT 
                id,
                source,
                source_url,
                report_text,
                event_type,
                report_datetime,
                city,
                state,
                latitude,
                longitude,
                verification_result,
                verification_score,
                verification_reason,
                trust_score,
                trust_reason,
                ai_confidence,
                duplicate_status,
                duplicate_similarity_score,
                created_at
            FROM weather_reports
            WHERE {where_sql}
            ORDER BY report_datetime DESC;
        """
        cursor.execute(query, tuple(params))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        records = []
        for r in rows:
            records.append({
                "id": r["id"],
                "source": r["source"] or "Citizen Report",
                "source_url": r["source_url"] or "",
                "report_text": r["report_text"] or "",
                "event_type": r["event_type"] or "",
                "report_datetime": r["report_datetime"].strftime("%Y-%m-%d %H:%M:%S") if r["report_datetime"] else "",
                "city": r["city"] or "",
                "state": r["state"] or "",
                "latitude": float(r["latitude"]) if r["latitude"] is not None else "",
                "longitude": float(r["longitude"]) if r["longitude"] is not None else "",
                "verification_result": r["verification_result"] or "Unverified",
                "verification_score": float(r["verification_score"]) if r["verification_score"] is not None else "",
                "verification_reason": r["verification_reason"] or "",
                "trust_score": float(r["trust_score"]) if r["trust_score"] is not None else "",
                "trust_reason": r["trust_reason"] or "",
                "ai_confidence": float(r["ai_confidence"]) if r["ai_confidence"] is not None else "",
                "duplicate_status": r["duplicate_status"] or "Unique",
                "duplicate_similarity_score": float(r["duplicate_similarity_score"]) if r["duplicate_similarity_score"] is not None else "",
                "created_at": r["created_at"].strftime("%Y-%m-%d %H:%M:%S") if r["created_at"] else ""
            })

        return True, records

    except Exception as e:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        return False, str(e)


def fetch_filtered_observations_for_export(start_date=None, end_date=None, event_type=None, state=None, city=None):
    """
    Fetch weather observations from api_weather_data table for CSV export.
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        where_clauses = ["1=1"]
        params = []

        if start_date and start_date.strip():
            where_clauses.append("recorded_at >= %s")
            params.append(start_date.strip() + " 00:00:00")

        if end_date and end_date.strip():
            where_clauses.append("recorded_at <= %s")
            params.append(end_date.strip() + " 23:59:59")

        if event_type and event_type.strip() and event_type.strip().lower() != 'all':
            where_clauses.append("event_type = %s")
            params.append(event_type.strip())

        if state and state.strip() and state.strip().lower() != 'all':
            where_clauses.append("state = %s")
            params.append(state.strip())

        if city and city.strip():
            where_clauses.append("LOWER(city) LIKE LOWER(%s)")
            params.append(f"%{city.strip()}%")

        where_sql = " AND ".join(where_clauses)

        query = f"""
            SELECT 
                city,
                state,
                latitude,
                longitude,
                temperature,
                humidity,
                wind_speed,
                weather_condition,
                weather_description,
                event_type,
                event_confidence,
                recorded_at
            FROM api_weather_data
            WHERE {where_sql}
            ORDER BY recorded_at DESC;
        """
        cursor.execute(query, tuple(params))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        records = []
        for r in rows:
            records.append({
                "city": r["city"] or "",
                "state": r["state"] or "",
                "latitude": float(r["latitude"]) if r["latitude"] is not None else "",
                "longitude": float(r["longitude"]) if r["longitude"] is not None else "",
                "temperature": float(r["temperature"]) if r["temperature"] is not None else "",
                "humidity": float(r["humidity"]) if r["humidity"] is not None else "",
                "wind_speed": float(r["wind_speed"]) if r["wind_speed"] is not None else "",
                "weather_condition": r["weather_condition"] or "",
                "weather_description": r["weather_description"] or "",
                "event_type": r["event_type"] or "Normal Weather",
                "event_confidence": float(r["event_confidence"]) if r["event_confidence"] is not None else "",
                "recorded_at": r["recorded_at"].strftime("%Y-%m-%d %H:%M:%S") if r["recorded_at"] else ""
            })

        return True, records

    except Exception as e:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        return False, str(e)


def fetch_filtered_alerts_for_export(event_type=None, severity=None, status=None, state=None, city=None):
    """
    Fetch weather alerts from weather_alerts table for CSV export.
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        where_clauses = ["1=1"]
        params = []

        if event_type and event_type.strip() and event_type.strip().lower() != 'all':
            where_clauses.append("event_type = %s")
            params.append(event_type.strip())

        if severity and severity.strip() and severity.strip().lower() != 'all':
            where_clauses.append("severity = %s")
            params.append(severity.strip().upper())

        if status and status.strip() and status.strip().lower() != 'all':
            where_clauses.append("status = %s")
            params.append(status.strip().capitalize())

        if state and state.strip() and state.strip().lower() != 'all':
            where_clauses.append("state = %s")
            params.append(state.strip())

        if city and city.strip():
            where_clauses.append("LOWER(city) LIKE LOWER(%s)")
            params.append(f"%{city.strip()}%")

        where_sql = " AND ".join(where_clauses)

        query = f"""
            SELECT 
                id as alert_id,
                event_type,
                severity,
                city,
                state,
                latitude,
                longitude,
                event_confidence,
                status,
                detected_at,
                resolved_at
            FROM weather_alerts
            WHERE {where_sql}
            ORDER BY detected_at DESC;
        """
        cursor.execute(query, tuple(params))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        records = []
        for r in rows:
            records.append({
                "alert_id": r["alert_id"],
                "event_type": r["event_type"],
                "severity": r["severity"],
                "city": r["city"],
                "state": r["state"] or "",
                "latitude": float(r["latitude"]) if r["latitude"] is not None else "",
                "longitude": float(r["longitude"]) if r["longitude"] is not None else "",
                "event_confidence": float(r["event_confidence"]) if r["event_confidence"] is not None else "",
                "status": r["status"],
                "detected_at": r["detected_at"].strftime("%Y-%m-%d %H:%M:%S") if r["detected_at"] else "",
                "resolved_at": r["resolved_at"].strftime("%Y-%m-%d %H:%M:%S") if r["resolved_at"] else ""
            })

        return True, records

    except Exception as e:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        return False, str(e)


def fetch_admin_audit_for_export():
    """
    Fetch admin_actions records for admin CSV export.
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        query = """
            SELECT 
                id as action_id,
                report_id,
                action_type,
                previous_verification,
                new_verification,
                reason,
                performed_by,
                action_datetime
            FROM admin_actions
            ORDER BY action_datetime DESC;
        """
        cursor.execute(query)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        records = []
        for r in rows:
            records.append({
                "action_id": r["action_id"],
                "report_id": r["report_id"],
                "action_type": r["action_type"],
                "previous_verification": r["previous_verification"] or "Unverified",
                "new_verification": r["new_verification"] or "",
                "reason": r["reason"] or "",
                "performed_by": r["performed_by"] or "Admin",
                "action_datetime": r["action_datetime"].strftime("%Y-%m-%d %H:%M:%S") if r["action_datetime"] else ""
            })

        return True, records

    except Exception as e:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        return False, str(e)


def generate_weather_intelligence_summary():
    """
    Generate structured Weather Intelligence Report from empirical database data.
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # 1. National Overview
        cursor.execute("SELECT COUNT(*) as cnt FROM weather_reports;")
        total_reports = cursor.fetchone()["cnt"]

        cursor.execute("SELECT COUNT(*) as cnt FROM api_weather_data;")
        total_obs = cursor.fetchone()["cnt"]

        cursor.execute("SELECT COUNT(*) as cnt FROM weather_alerts WHERE status = 'Active';")
        active_alerts = cursor.fetchone()["cnt"]

        cursor.execute("SELECT COUNT(DISTINCT state) as cnt FROM (SELECT state FROM weather_reports WHERE state IS NOT NULL AND state != '' UNION SELECT state FROM api_weather_data WHERE state IS NOT NULL AND state != '') t;")
        states_count = cursor.fetchone()["cnt"]

        cursor.execute("SELECT COUNT(DISTINCT city) as cnt FROM (SELECT city FROM weather_reports WHERE city IS NOT NULL AND city != '' UNION SELECT city FROM api_weather_data WHERE city IS NOT NULL AND city != '') t;")
        cities_count = cursor.fetchone()["cnt"]

        cursor.execute("SELECT AVG(trust_score) as avg_trust FROM weather_reports WHERE trust_score IS NOT NULL;")
        row_t = cursor.fetchone()
        avg_trust = round(float(row_t["avg_trust"]), 1) if row_t and row_t["avg_trust"] is not None else 0.0

        national_overview = {
            "total_reports": total_reports,
            "total_observations": total_obs,
            "active_alerts": active_alerts,
            "states_represented": states_count,
            "cities_represented": cities_count,
            "average_trust_score": avg_trust
        }

        # 2. Major Weather Events
        cursor.execute("""
            SELECT event_type, COUNT(*) as count 
            FROM (
                SELECT event_type FROM weather_reports WHERE event_type IS NOT NULL AND event_type != '' 
                UNION ALL 
                SELECT event_type FROM api_weather_data WHERE event_type IS NOT NULL AND event_type != ''
            ) t 
            GROUP BY event_type 
            ORDER BY count DESC 
            LIMIT 5;
        """)
        top_events = cursor.fetchall()

        cursor.execute("""
            SELECT city, state, event_type, MAX(event_confidence) as max_conf 
            FROM api_weather_data 
            WHERE event_confidence >= 75.0 
            GROUP BY city, state, event_type 
            ORDER BY max_conf DESC 
            LIMIT 5;
        """)
        highest_conf_events = cursor.fetchall()

        cursor.execute("""
            SELECT state, COUNT(*) as count 
            FROM (
                SELECT state FROM weather_reports WHERE state IS NOT NULL AND state != '' 
                UNION ALL 
                SELECT state FROM api_weather_data WHERE state IS NOT NULL AND state != ''
            ) t 
            GROUP BY state 
            ORDER BY count DESC 
            LIMIT 5;
        """)
        top_states = cursor.fetchall()

        cursor.execute("""
            SELECT city, COUNT(*) as count 
            FROM (
                SELECT city FROM weather_reports WHERE city IS NOT NULL AND city != '' 
                UNION ALL 
                SELECT city FROM api_weather_data WHERE city IS NOT NULL AND city != ''
            ) t 
            GROUP BY city 
            ORDER BY count DESC 
            LIMIT 5;
        """)
        top_cities = cursor.fetchall()

        major_events = {
            "most_common_events": top_events,
            "highest_confidence_events": highest_conf_events,
            "top_states": top_states,
            "top_cities": top_cities
        }

        # 3. Verification Overview
        cursor.execute("""
            SELECT 
                COUNT(CASE WHEN verification_result = 'Likely Consistent' OR verification_status = 'Likely Consistent' THEN 1 END) as verified_cnt,
                COUNT(CASE WHEN verification_result = 'Needs Verification' OR verification_status = 'Needs Verification' THEN 1 END) as needs_ver_cnt,
                COUNT(CASE WHEN verification_result = 'Suspicious' OR verification_status = 'Suspicious' THEN 1 END) as suspicious_cnt,
                COUNT(CASE WHEN verification_result = 'Unverified' OR verification_status = 'Unverified' OR (verification_result IS NULL AND verification_status IS NULL) THEN 1 END) as unverified_cnt
            FROM weather_reports;
        """)
        ver_row = cursor.fetchone()
        verification_overview = {
            "verified_reports": ver_row["verified_cnt"] if ver_row else 0,
            "needs_verification": ver_row["needs_ver_cnt"] if ver_row else 0,
            "suspicious": ver_row["suspicious_cnt"] if ver_row else 0,
            "unverified": ver_row["unverified_cnt"] if ver_row else 0
        }

        # 4. Data Quality
        cursor.execute("SELECT COUNT(*) as cnt FROM weather_reports WHERE duplicate_status = 'Unique' OR duplicate_status IS NULL;")
        unique_cnt = cursor.fetchone()["cnt"]

        cursor.execute("SELECT COUNT(*) as cnt FROM weather_reports WHERE duplicate_status != 'Unique' AND duplicate_status IS NOT NULL;")
        dup_cnt = cursor.fetchone()["cnt"]

        data_quality = {
            "unique_reports": unique_cnt,
            "potential_duplicates": dup_cnt,
            "average_trust_score": avg_trust
        }

        # 5. Alert Status
        cursor.execute("""
            SELECT 
                COUNT(CASE WHEN status = 'Active' THEN 1 END) as active_cnt,
                COUNT(CASE WHEN status = 'Resolved' THEN 1 END) as resolved_cnt,
                COUNT(CASE WHEN status = 'Active' AND severity = 'HIGH' THEN 1 END) as high_cnt,
                COUNT(CASE WHEN status = 'Active' AND severity = 'MEDIUM' THEN 1 END) as med_cnt,
                COUNT(CASE WHEN status = 'Active' AND severity = 'LOW' THEN 1 END) as low_cnt
            FROM weather_alerts;
        """)
        alert_row = cursor.fetchone()
        alert_status_summary = {
            "active_alerts": alert_row["active_cnt"] if alert_row else 0,
            "resolved_alerts": alert_row["resolved_cnt"] if alert_row else 0,
            "high_severity": alert_row["high_cnt"] if alert_row else 0,
            "medium_severity": alert_row["med_cnt"] if alert_row else 0,
            "low_severity": alert_row["low_cnt"] if alert_row else 0
        }

        # 6. Key Observations (Automated Synthesized Cautious Phrases)
        key_observations = []

        if active_alerts > 0:
            cursor.execute("SELECT city, state, event_type, severity FROM weather_alerts WHERE status = 'Active' ORDER BY severity DESC, detected_at DESC LIMIT 3;")
            active_list = cursor.fetchall()
            for a in active_list:
                key_observations.append(f"Potential {a['event_type'].lower()} conditions detected in {a['city']} ({a['state']}) - Severity: {a['severity']}.")
        else:
            key_observations.append("No critical active weather alerts currently active across monitored regions.")

        if total_reports > 0:
            key_observations.append(f"Ingested {total_reports} citizen and multi-source public weather reports across {cities_count} cities with an average source trust score of {avg_trust}%.")
        
        if total_obs > 0:
            key_observations.append(f"Automated OpenWeatherMap API background service has cataloged {total_obs} meteorological observations across Indian states.")

        cursor.close()
        conn.close()

        return True, {
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "national_overview": national_overview,
            "major_events": major_events,
            "verification_overview": verification_overview,
            "data_quality": data_quality,
            "alert_status": alert_status_summary,
            "key_observations": key_observations
        }

    except Exception as e:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        return False, str(e)




