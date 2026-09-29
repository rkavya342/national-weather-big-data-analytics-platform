import logging
import threading
from datetime import datetime
from services.weather_api import fetch_city_weather
from database.db import save_api_weather_data

# Configure logger
logger = logging.getLogger("weather_ingestion")

# Lock to prevent overlapping ingestion jobs
_ingestion_lock = threading.Lock()

# List of major Indian cities for automatic weather ingestion
DEFAULT_INDIAN_CITIES = [
    "Chennai",
    "Madurai",
    "Bengaluru",
    "Hyderabad",
    "Mumbai",
    "Delhi",
    "Kolkata",
    "Pune",
    "Ahmedabad",
    "Jaipur",
    "Lucknow",
    "Kochi",
    "Coimbatore",
    "Visakhapatnam",
    "Bhopal"
]

# Thread-safe global ingestion status tracker
LATEST_INGESTION_STATUS = {
    "status": "idle",
    "total_cities": len(DEFAULT_INDIAN_CITIES),
    "success_count": 0,
    "failed_count": 0,
    "failed_cities": [],
    "timestamp": None,
    "automatic_enabled": True,
    "interval_minutes": 15
}


def get_latest_ingestion_status():
    """Return latest ingestion status dictionary."""
    return LATEST_INGESTION_STATUS.copy()


def run_weather_ingestion(cities=None):
    """
    Execute one complete weather data ingestion cycle for configured cities.
    - Calls OpenWeatherMap API for each city
    - Prevents duplicates within the same run
    - Stores successful weather observations in PostgreSQL api_weather_data table
    - Logs ingestion progress securely (without API keys)
    - Updates LATEST_INGESTION_STATUS
    """
    if not _ingestion_lock.acquire(blocking=False):
        logger.info("Weather ingestion is already in progress. Skipping overlapping run.")
        status_copy = get_latest_ingestion_status()
        status_copy["in_progress"] = True
        return status_copy

    try:
        if cities is None:
            cities = DEFAULT_INDIAN_CITIES

        logger.info("=== Starting Weather Data Ingestion Run (%d cities) ===", len(cities))

        processed_cities = set()
        success_count = 0
        failed_count = 0
        failed_cities = []
        ingested_records = []

        for city in cities:
            city_clean = city.strip()
            city_key = city_clean.lower()

            # Duplicate protection within the same ingestion run
            if city_key in processed_cities:
                continue
            processed_cities.add(city_key)

            # Call OpenWeatherMap API service
            success, result = fetch_city_weather(city_clean)

            if success:
                # Save observation into PostgreSQL api_weather_data table
                db_success, db_res = save_api_weather_data(result)
                if db_success:
                    success_count += 1
                    ingested_records.append(result)
                    logger.info("Successfully ingested weather observation for city: %s (Temp: %.1f°C)", city_clean, result.get("temperature", 0.0))
                else:
                    failed_count += 1
                    reason = f"Database save error: {db_res}"
                    failed_cities.append({"city": city_clean, "reason": reason})
                    logger.warning("Failed to save weather data for city %s: %s", city_clean, reason)
            else:
                failed_count += 1
                failed_cities.append({"city": city_clean, "reason": result})
                logger.warning("Failed API fetch for city %s: %s", city_clean, result)

        timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Update global status tracker
        LATEST_INGESTION_STATUS.update({
            "status": "success" if success_count > 0 else "error",
            "total_cities": len(processed_cities),
            "success_count": success_count,
            "failed_count": failed_count,
            "failed_cities": failed_cities,
            "timestamp": timestamp_str,
            "automatic_enabled": True,
            "interval_minutes": 15
        })

        logger.info(
            "=== Weather Data Ingestion Run Completed: Total=%d, Success=%d, Failed=%d at %s ===",
            len(processed_cities),
            success_count,
            failed_count,
            timestamp_str
        )

        summary_result = LATEST_INGESTION_STATUS.copy()

        # Broadcast real-time SocketIO 'weather_update' event
        try:
            from socketio_instance import broadcast_weather_update
            broadcast_weather_update(summary_result)
        except Exception:
            pass

        return summary_result
    finally:
        _ingestion_lock.release()
