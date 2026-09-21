import os
import requests
from datetime import datetime
from dotenv import load_dotenv, find_dotenv


def _reload_env():
    """Ensure environment variables from .env file are loaded with override."""
    env_file = find_dotenv()
    if env_file:
        load_dotenv(env_file, override=True)
    else:
        load_dotenv(override=True)


# Load env on module import
_reload_env()


def fetch_city_weather(city_name):
    """
    Call OpenWeatherMap Current Weather API for a given city.
    Returns tuple: (success: bool, data_or_error: dict | str)
    """
    _reload_env()
    api_key = os.getenv("OPENWEATHER_API_KEY", "").strip()

    if not api_key:
        return False, "OpenWeatherMap API Key is missing. Please set OPENWEATHER_API_KEY in the .env file."

    if not city_name or not city_name.strip():
        return False, "Please enter a valid city name."

    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {
        "q": city_name.strip(),
        "appid": api_key,
        "units": "metric"
    }

    try:
        response = requests.get(url, params=params, timeout=10)

        if response.status_code == 200:
            data = response.json()
            weather_list = data.get("weather", [{}])
            main_weather = weather_list[0] if weather_list else {}

            parsed_data = {
                "source": "OpenWeatherMap API",
                "city": data.get("name", city_name.strip()),
                "country": data.get("sys", {}).get("country", ""),
                "state": "",  # OpenWeatherMap current weather API does not return state directly
                "latitude": data.get("coord", {}).get("lat"),
                "longitude": data.get("coord", {}).get("lon"),
                "temperature": data.get("main", {}).get("temp"),
                "humidity": data.get("main", {}).get("humidity"),
                "wind_speed": data.get("wind", {}).get("speed"),
                "weather_condition": main_weather.get("main", "Unknown"),
                "weather_description": main_weather.get("description", "").title(),
                "recorded_at": datetime.fromtimestamp(data.get("dt", datetime.now().timestamp()))
            }
            return True, parsed_data
        elif response.status_code == 404:
            return False, f"City '{city_name.strip()}' was not found by OpenWeatherMap API. Please check the spelling."
        elif response.status_code == 401:
            return False, "Invalid OpenWeatherMap API Key. Please verify your key in the .env file."
        else:
            return False, f"OpenWeatherMap API returned status code {response.status_code}: {response.text}"

    except requests.exceptions.Timeout:
        return False, "Request to OpenWeatherMap API timed out. Please try again later."
    except requests.exceptions.RequestException as e:
        return False, f"Network error connecting to OpenWeatherMap API: {str(e)}"
    except Exception as e:
        return False, f"Unexpected error processing weather data: {str(e)}"


def fetch_weather_by_coords(lat, lon):
    """
    Call OpenWeatherMap Current Weather API for latitude and longitude coordinates.
    Returns tuple: (success: bool, data_or_error: dict | str)
    """
    _reload_env()
    api_key = os.getenv("OPENWEATHER_API_KEY", "").strip()

    if not api_key:
        return False, "OpenWeatherMap API Key is missing. Please set OPENWEATHER_API_KEY in the .env file."

    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {
        "lat": lat,
        "lon": lon,
        "appid": api_key,
        "units": "metric"
    }

    try:
        response = requests.get(url, params=params, timeout=10)

        if response.status_code == 200:
            data = response.json()
            weather_list = data.get("weather", [{}])
            main_weather = weather_list[0] if weather_list else {}

            parsed_data = {
                "source": "Map Click Weather Lookup",
                "city": data.get("name") or f"Location ({float(lat):.2f}, {float(lon):.2f})",
                "country": data.get("sys", {}).get("country", ""),
                "latitude": data.get("coord", {}).get("lat", float(lat)),
                "longitude": data.get("coord", {}).get("lon", float(lon)),
                "temperature": data.get("main", {}).get("temp"),
                "humidity": data.get("main", {}).get("humidity"),
                "wind_speed": data.get("wind", {}).get("speed"),
                "weather_condition": main_weather.get("main", "Unknown"),
                "weather_description": main_weather.get("description", "").title(),
                "recorded_at": datetime.fromtimestamp(data.get("dt", datetime.now().timestamp())).strftime("%Y-%m-%d %H:%M:%S")
            }
            return True, parsed_data
        else:
            return False, f"Weather API returned status code {response.status_code}"
    except Exception as e:
        return False, f"Error querying location weather: {str(e)}"

