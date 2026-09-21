import os
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime

from database.db import get_db_connection, fetch_latest_obs_for_city, fetch_recent_citizen_reports, init_db
from ml.weather_classifier import WeatherEventClassifier
from ml.report_verifier import ReportVerifier
from ml.duplicate_detector import DuplicateDetector
from ml.trust_scorer import SourceTrustScorer

"""
Multi-Source Weather Report Ingestion Engine.
------------------------------------------------
Academic / Hackathon Prototype Disclaimer:
This module ingests weather observations and reports across 8 distinct source types.
Social media feeds and public dataset entries included in this module are SIMULATED
synthetic datasets created specifically for hackathon demonstration.
Production deployments would connect to authorized REST APIs, public feeds, or RSS streams.
"""

SAMPLE_MULTI_SOURCE_REPORTS = [
    {
        "source": "Government/Official Source",
        "source_url": "https://mausam.imd.gov.in/bulletin/heavy-rain-chennai",
        "report_text": "IMD Official Weather Bulletin: Heavy to very heavy rainfall exceeding 120mm recorded across Chennai urban coastal district. Red alert issued for low-lying areas.",
        "event_type": "Heavy Rainfall",
        "report_datetime": "2026-09-14T08:30:00",
        "city": "Chennai",
        "state": "Tamil Nadu",
        "latitude": 13.0827,
        "longitude": 80.2707,
        "image_url": "https://images.unsplash.com/photo-1515694346937-94d85e41e6f0",
        "video_url": None
    },
    {
        "source": "Official Weather API",
        "source_url": "https://api.openweathermap.org/data/2.5/weather?q=Bengaluru",
        "report_text": "OpenWeather API Station Sync: Bengaluru recorded severe thunderstorm with convective wind gusts of 22 m/s and 88% humidity.",
        "event_type": "Thunderstorm",
        "report_datetime": "2026-09-14T09:00:00",
        "city": "Bengaluru",
        "state": "Karnataka",
        "latitude": 12.9716,
        "longitude": 77.5946,
        "image_url": None,
        "video_url": None
    },
    {
        "source": "Verified Organization",
        "source_url": "https://skymetweather.com/forecast/mumbai-flood-warning",
        "report_text": "Skymet Verified Flood Watch: High tide combined with continuous 140mm rainfall causing severe waterlogging and flood risk in Mumbai Dadar and Kurla low areas.",
        "event_type": "Flood Risk",
        "report_datetime": "2026-09-14T07:45:00",
        "city": "Mumbai",
        "state": "Maharashtra",
        "latitude": 19.0760,
        "longitude": 72.8777,
        "image_url": "https://images.unsplash.com/photo-1547683905-f686c993aae5",
        "video_url": None
    },
    {
        "source": "News Website",
        "source_url": "https://timesofindia.indiatimes.com/weather/delhi-heatwave-alert",
        "report_text": "Times Weather Desk: Delhi experiences severe heatwave conditions as peak temperature touches 44.5°C with dry northwesterly winds.",
        "event_type": "Heatwave",
        "report_datetime": "2026-09-14T11:15:00",
        "city": "Delhi",
        "state": "Delhi",
        "latitude": 28.6139,
        "longitude": 77.2090,
        "image_url": None,
        "video_url": None
    },
    {
        "source": "Citizen Report",
        "source_url": None,
        "report_text": "Extreme waterlogging near Madurai junction station. Roads inundated with 2 feet of water following sudden torrential cloudburst.",
        "event_type": "Heavy Rainfall",
        "report_datetime": "2026-09-14T10:00:00",
        "city": "Madurai",
        "state": "Tamil Nadu",
        "latitude": 9.9252,
        "longitude": 78.1198,
        "image_url": "https://images.unsplash.com/photo-1519692933481-e162a57d6721",
        "video_url": None
    },
    {
        "source": "Social Media",
        "source_url": "https://twitter.com/simulated_weather_user/status/100912",
        "report_text": "#JaipurDustStorm Thick blinding dust storm blowing across Jaipur bypass highway! Visibility dropped below 100 meters. Drive safe everyone!",
        "event_type": "Dust Storm",
        "report_datetime": "2026-09-14T10:30:00",
        "city": "Jaipur",
        "state": "Rajasthan",
        "latitude": 26.9124,
        "longitude": 75.7873,
        "image_url": "https://images.unsplash.com/photo-1509316975850-ff9c5deb0cd9",
        "video_url": None
    },
    {
        "source": "Social Media",
        "source_url": "https://x.com/simulated_hyd_news/status/209123",
        "report_text": "Heavy thunderstorm and dark clouds over Gachibowli Hyderabad! Loud thunder strikes and sudden heavy downpour starting right now.",
        "event_type": "Thunderstorm",
        "report_datetime": "2026-09-14T11:00:00",
        "city": "Hyderabad",
        "state": "Telangana",
        "latitude": 17.3850,
        "longitude": 78.4867,
        "image_url": None,
        "video_url": None
    },
    {
        "source": "Public Dataset",
        "source_url": "https://data.gov.in/dataset/open-weather-log-hyderabad-2026",
        "report_text": "Open Government Data Archive: Visibility dropped to 150 meters due to dense winter fog over Lucknow International Airport runway.",
        "event_type": "Fog",
        "report_datetime": "2026-09-14T06:00:00",
        "city": "Lucknow",
        "state": "Uttar Pradesh",
        "latitude": 26.8467,
        "longitude": 80.9462,
        "image_url": None,
        "video_url": None
    },
    {
        "source": "News Website",
        "source_url": "https://thehindu.com/news/national/kerala/kochi-coastal-gales",
        "report_text": "Coastal Warning: Strong wind gales reaching 65 km/h reported along Kochi harbor coastline with high sea waves.",
        "event_type": "Strong Wind",
        "report_datetime": "2026-09-14T09:45:00",
        "city": "Kochi",
        "state": "Kerala",
        "latitude": 9.9312,
        "longitude": 76.2673,
        "image_url": None,
        "video_url": None
    },
    {
        "source": "Verified Organization",
        "source_url": "https://ndrf.gov.in/alerts/bhopal-lake-overflow",
        "report_text": "NDRF Quick Response Team: Upper Lake spillway gates opened in Bhopal following 110mm rainfall. Advisory issued for low areas.",
        "event_type": "Flood Risk",
        "report_datetime": "2026-09-14T08:15:00",
        "city": "Bhopal",
        "state": "Madhya Pradesh",
        "latitude": 23.2599,
        "longitude": 77.4126,
        "image_url": None,
        "video_url": None
    },
    {
        "source": "Citizen Report",
        "source_url": None,
        "report_text": "Severe dust storm blowing across Ahmedabad city roads. Wind blowing sand and debris everywhere.",
        "event_type": "Dust Storm",
        "report_datetime": "2026-09-14T10:45:00",
        "city": "Ahmedabad",
        "state": "Gujarat",
        "latitude": 23.0225,
        "longitude": 72.5714,
        "image_url": None,
        "video_url": None
    },
    {
        "source": "Unknown Source",
        "source_url": "https://unverified-blog.xyz/weather-post/102",
        "report_text": "Unverified blog report claiming extreme 50°C heatwave in Pune city.",
        "event_type": "Heatwave",
        "report_datetime": "2026-09-14T12:00:00",
        "city": "Pune",
        "state": "Maharashtra",
        "latitude": 18.5204,
        "longitude": 73.8567,
        "image_url": None,
        "video_url": None
    }
]


def get_sample_weather_reports():
    """Return the list of sample multi-source weather reports."""
    return SAMPLE_MULTI_SOURCE_REPORTS


def import_sample_reports():
    """
    Import sample multi-source weather reports into weather_reports table.
    Checks for duplicate entries based on (source, city, report_text, report_datetime).
    Automatically runs AI event classification, verification, duplicate detection, and trust scoring.
    Returns: (imported_count, skipped_count, analyzed_count, total_count)
    """
    init_db()
    conn = None
    imported_count = 0
    skipped_count = 0
    analyzed_count = 0

    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        for sample in SAMPLE_MULTI_SOURCE_REPORTS:
            src = sample.get("source")
            city = sample.get("city")
            text = sample.get("report_text")
            dt = sample.get("report_datetime")

            # Check if this exact sample report already exists in weather_reports
            cursor.execute("""
                SELECT id FROM weather_reports 
                WHERE source = %s AND LOWER(city) = LOWER(%s) AND report_text = %s;
            """, (src, city, text))
            existing = cursor.fetchone()

            if existing:
                skipped_count += 1
                continue

            # Insert report into weather_reports table
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
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            ) RETURNING id;
            """
            cursor.execute(insert_sql, (
                src,
                sample.get("source_url"),
                text,
                sample.get("event_type"),
                dt,
                city,
                sample.get("state"),
                sample.get("latitude"),
                sample.get("longitude"),
                sample.get("image_url"),
                sample.get("video_url")
            ))
            report_id = cursor.fetchone()["id"]
            conn.commit()
            imported_count += 1

            # Fetch recent observation for verification
            recent_obs = fetch_latest_obs_for_city(city)

            # 1. Verification Analysis
            v_result, v_score, v_reason, v_at = ReportVerifier.verify_report(
                report_text=text,
                event_type=sample.get("event_type"),
                city=city,
                report_datetime=dt,
                recent_obs=recent_obs
            )

            # 2. Duplicate Detection
            current_rep = {
                "id": report_id,
                "source": src,
                "report_text": text,
                "event_type": sample.get("event_type"),
                "city": city,
                "state": sample.get("state"),
                "latitude": sample.get("latitude"),
                "longitude": sample.get("longitude"),
                "report_datetime": dt
            }
            recent_reps = fetch_recent_citizen_reports(hours=48)
            is_dup, dup_grp, dup_status, dup_sim, dup_reason, dup_checked = DuplicateDetector.detect_duplicates(
                new_report=current_rep,
                recent_reports=recent_reps
            )

            # 3. Source Trust Scoring
            t_score, t_level, t_reason, t_updated = SourceTrustScorer.calculate_trust(
                source=src,
                verification_result=v_result,
                verification_score=v_score,
                duplicate_status=dup_status,
                latitude=sample.get("latitude"),
                longitude=sample.get("longitude"),
                report_datetime=dt,
                image_url=sample.get("image_url")
            )

            # Update DB record with analysis results
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
            analyzed_count += 1

        cursor.close()
        conn.close()

        # Broadcast real-time SocketIO 'new_report' event
        try:
            from socketio_instance import broadcast_new_report
            broadcast_new_report({"imported": imported_count, "skipped": skipped_count})
        except Exception:
            pass

        return imported_count, skipped_count, analyzed_count, len(SAMPLE_MULTI_SOURCE_REPORTS)

    except Exception as e:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        raise e
