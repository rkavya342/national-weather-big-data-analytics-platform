import re
import html
import logging
import requests
from datetime import datetime
from psycopg2.extras import RealDictCursor

from database.db import (
    get_db_connection,
    fetch_latest_obs_for_city,
    fetch_recent_citizen_reports,
    init_db
)
from ml.weather_classifier import WeatherEventClassifier
from ml.report_verifier import ReportVerifier
from ml.duplicate_detector import DuplicateDetector
from ml.trust_scorer import SourceTrustScorer

logger = logging.getLogger("mastodon_ingestion")

SUPPORTED_MASTODON_TAGS = ["IMD", "WeatherUpdate", "RainAlert", "Monsoon"]

INDIAN_LOCATION_MAP = {
    "mumbai": {"city": "Mumbai", "state": "Maharashtra", "lat": 19.0760, "lon": 72.8777},
    "delhi": {"city": "Delhi", "state": "Delhi", "lat": 28.6139, "lon": 77.2090},
    "bengaluru": {"city": "Bengaluru", "state": "Karnataka", "lat": 12.9716, "lon": 77.5946},
    "bangalore": {"city": "Bengaluru", "state": "Karnataka", "lat": 12.9716, "lon": 77.5946},
    "chennai": {"city": "Chennai", "state": "Tamil Nadu", "lat": 13.0827, "lon": 80.2707},
    "hyderabad": {"city": "Hyderabad", "state": "Telangana", "lat": 17.3850, "lon": 78.4867},
    "kolkata": {"city": "Kolkata", "state": "West Bengal", "lat": 22.5726, "lon": 88.3639},
    "pune": {"city": "Pune", "state": "Maharashtra", "lat": 18.5204, "lon": 73.8567},
    "ahmedabad": {"city": "Ahmedabad", "state": "Gujarat", "lat": 23.0225, "lon": 72.5714},
    "jaipur": {"city": "Jaipur", "state": "Rajasthan", "lat": 26.9124, "lon": 75.7873},
    "lucknow": {"city": "Lucknow", "state": "Uttar Pradesh", "lat": 26.8467, "lon": 80.9462},
    "kochi": {"city": "Kochi", "state": "Kerala", "lat": 9.9312, "lon": 76.2673},
    "cochin": {"city": "Kochi", "state": "Kerala", "lat": 9.9312, "lon": 76.2673},
    "coimbatore": {"city": "Coimbatore", "state": "Tamil Nadu", "lat": 11.0168, "lon": 76.9558},
    "madurai": {"city": "Madurai", "state": "Tamil Nadu", "lat": 9.9252, "lon": 78.1198},
    "visakhapatnam": {"city": "Visakhapatnam", "state": "Andhra Pradesh", "lat": 17.6868, "lon": 83.2185},
    "vizag": {"city": "Visakhapatnam", "state": "Andhra Pradesh", "lat": 17.6868, "lon": 83.2185},
    "bhopal": {"city": "Bhopal", "state": "Madhya Pradesh", "lat": 23.2599, "lon": 77.4126},
    "kerala": {"city": "Kerala Region", "state": "Kerala", "lat": 10.8505, "lon": 76.2711},
    "goa": {"city": "Goa", "state": "Goa", "lat": 15.2993, "lon": 74.1240},
    "assam": {"city": "Assam Region", "state": "Assam", "lat": 26.2006, "lon": 92.9376},
    "shimla": {"city": "Shimla", "state": "Himachal Pradesh", "lat": 31.1048, "lon": 77.1734},
    "patna": {"city": "Patna", "state": "Bihar", "lat": 25.5941, "lon": 85.1376},
    "bhubaneswar": {"city": "Bhubaneswar", "state": "Odisha", "lat": 20.2961, "lon": 85.8245},
    "nagpur": {"city": "Nagpur", "state": "Maharashtra", "lat": 21.1458, "lon": 79.0882},
    "surat": {"city": "Surat", "state": "Gujarat", "lat": 21.1702, "lon": 72.8311}
}

MASTODON_INGESTION_STATUS = {
    "status": "idle",
    "last_run": None,
    "total_tags": len(SUPPORTED_MASTODON_TAGS),
    "received": 0,
    "inserted": 0,
    "duplicates": 0,
    "errors": 0,
    "error_message": None
}


def get_mastodon_ingestion_status():
    """Return latest Mastodon ingestion status dictionary."""
    return MASTODON_INGESTION_STATUS.copy()


def clean_html(raw_html):
    """Clean HTML content from Mastodon to plain text."""
    if not raw_html:
        return ""
    text = re.sub(r'<[^>]+>', ' ', str(raw_html))
    text = html.unescape(text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def extract_location_from_text(text):
    """
    Extract location information from text if present.
    Returns tuple: (city, state, lat, lon) or (None, None, None, None)
    Do NOT guess or invent a location if post does not mention one.
    """
    if not text:
        return None, None, None, None
    text_lower = text.lower()
    for loc_key, loc_info in INDIAN_LOCATION_MAP.items():
        if re.search(r'\b' + re.escape(loc_key) + r'\b', text_lower):
            return loc_info["city"], loc_info["state"], loc_info["lat"], loc_info["lon"]
    return None, None, None, None


def fetch_mastodon_posts_by_tag(tag, limit=10):
    """
    Fetch public Mastodon timeline statuses for a given hashtag.
    Returns list of parsed post dicts or empty list on network/API failure.
    """
    url = f"https://mastodon.social/api/v1/timelines/tag/{tag}?limit={limit}"
    headers = {
        "User-Agent": "NationalWeatherPlatform/1.0 (India Weather Intelligence Hub)"
    }
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            return resp.json()
        else:
            logger.warning("Mastodon API tag '%s' returned HTTP %d", tag, resp.status_code)
            return []
    except Exception as e:
        logger.warning("Mastodon API fetch exception for tag '%s': %s", tag, str(e))
        return []


def ingest_mastodon_reports(tags=None, limit_per_tag=10):
    """
    Execute ingestion of Mastodon weather statuses:
    1. Fetch statuses for supported tags (IMD, WeatherUpdate, RainAlert, Monsoon)
    2. Clean HTML content
    3. Extract location & metadata without inventing missing locations
    4. Check duplicates in PostgreSQL weather_reports
    5. Run ML classification, verification, duplicate detection & trust scoring
    6. Insert into weather_reports table
    """
    if tags is None:
        tags = SUPPORTED_MASTODON_TAGS

    init_db()
    conn = None
    received_count = 0
    inserted_count = 0
    duplicate_count = 0
    error_count = 0

    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        for tag in tags:
            posts = fetch_mastodon_posts_by_tag(tag, limit=limit_per_tag)
            received_count += len(posts)

            for post in posts:
                try:
                    post_id = str(post.get("id", ""))
                    post_url = post.get("url") or f"https://mastodon.social/tags/{tag}/{post_id}"
                    raw_content = post.get("content", "")
                    clean_text = clean_html(raw_content)

                    if not clean_text or len(clean_text) < 10:
                        continue

                    # Duplicate check in PostgreSQL weather_reports table by source_url or exact text
                    cursor.execute("""
                        SELECT id FROM weather_reports 
                        WHERE source_url = %s OR (source ILIKE '%%Mastodon%%' AND report_text = %s);
                    """, (post_url, clean_text))
                    if cursor.fetchone():
                        duplicate_count += 1
                        continue

                    # Parse datetime
                    created_at_raw = post.get("created_at")
                    parsed_dt = datetime.now()
                    if created_at_raw:
                        try:
                            parsed_dt = datetime.fromisoformat(str(created_at_raw).replace("Z", "+00:00")).replace(tzinfo=None)
                        except Exception:
                            parsed_dt = datetime.now()

                    # Extract location without inventing
                    city, state, lat, lon = extract_location_from_text(clean_text)

                    # Extract media attachments if present
                    media_attachments = post.get("media_attachments", [])
                    image_url = None
                    video_url = None
                    if media_attachments and isinstance(media_attachments, list):
                        for media in media_attachments:
                            m_type = media.get("type")
                            m_url = media.get("url") or media.get("preview_url")
                            if m_type == "image" and not image_url:
                                image_url = m_url
                            elif m_type in ["video", "gifv"] and not video_url:
                                video_url = m_url

                    # ML Event Classification
                    event_type, conf, _ = WeatherEventClassifier.classify(
                        temperature=25.0,
                        humidity=50.0,
                        wind_speed=2.0,
                        weather_condition="",
                        weather_description=clean_text
                    )

                    source_name = "Mastodon (Public Feed)"

                    # Insert post into weather_reports
                    insert_sql = """
                    INSERT INTO weather_reports (
                        source,
                        source_url,
                        report_text,
                        event_type,
                        report_datetime,
                        city,
                        state,
                        latitude,
                        longitude,
                        image_url,
                        video_url
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id;
                    """
                    cursor.execute(insert_sql, (
                        source_name,
                        post_url,
                        clean_text,
                        event_type,
                        parsed_dt,
                        city,
                        state,
                        lat,
                        lon,
                        image_url,
                        video_url
                    ))
                    new_id = cursor.fetchone()["id"]
                    conn.commit()

                    # AI Verification Analysis
                    recent_obs = fetch_latest_obs_for_city(city) if city else None
                    v_result, v_score, v_reason, v_at = ReportVerifier.verify_report(
                        report_text=clean_text,
                        event_type=event_type,
                        city=city or "India",
                        report_datetime=parsed_dt,
                        recent_obs=recent_obs
                    )

                    # Multi-signal Duplicate Analysis
                    current_rep = {
                        "id": new_id,
                        "source": source_name,
                        "report_text": clean_text,
                        "event_type": event_type,
                        "city": city,
                        "state": state,
                        "latitude": lat,
                        "longitude": lon,
                        "report_datetime": parsed_dt
                    }
                    recent_reps = fetch_recent_citizen_reports(hours=48)
                    is_dup, dup_grp, dup_status, dup_sim, dup_reason, dup_checked = DuplicateDetector.detect_duplicates(
                        new_report=current_rep,
                        recent_reports=recent_reps
                    )

                    # Source Trust Scoring
                    t_score, t_level, t_reason, t_updated = SourceTrustScorer.calculate_trust(
                        source=source_name,
                        verification_result=v_result,
                        verification_score=v_score,
                        duplicate_status=dup_status,
                        latitude=lat,
                        longitude=lon,
                        report_datetime=parsed_dt,
                        image_url=image_url
                    )

                    # Update record with ML scores
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
                        t_reason, t_updated, new_id
                    ))
                    conn.commit()
                    update_cursor.close()

                    inserted_count += 1

                except Exception as post_err:
                    error_count += 1
                    logger.warning("Error processing Mastodon post: %s", str(post_err))

        cursor.close()
        conn.close()

        timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        MASTODON_INGESTION_STATUS.update({
            "status": "success" if inserted_count > 0 or received_count > 0 else "idle",
            "last_run": timestamp_str,
            "received": received_count,
            "inserted": inserted_count,
            "duplicates": duplicate_count,
            "errors": error_count,
            "error_message": None
        })

        # Broadcast real-time SocketIO event
        try:
            from socketio_instance import broadcast_new_report
            broadcast_new_report({
                "source": "Mastodon (Public Feed)",
                "inserted": inserted_count,
                "duplicates": duplicate_count
            })
        except Exception:
            pass

    except Exception as e:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        error_msg = str(e)
        error_count += 1
        MASTODON_INGESTION_STATUS.update({
            "status": "error",
            "last_run": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "received": received_count,
            "inserted": inserted_count,
            "duplicates": duplicate_count,
            "errors": error_count,
            "error_message": error_msg
        })

    return MASTODON_INGESTION_STATUS.copy()
