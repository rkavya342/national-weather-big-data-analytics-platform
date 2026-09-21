import re
import logging
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime
import urllib3

# Suppress SSL certificate verification warnings for SACHET RSS endpoint
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger("sachet_ingestion")

SACHET_RSS_URL = "https://sachet.ndma.gov.in/cap_public_website/rss/rss_india.xml"
CAP_NS = {"cap": "urn:oasis:names:tc:emergency:cap:1.2"}

# Global cache headers for HTTP conditional requests
_LAST_ETAG = None
_LAST_MODIFIED = None

# Comprehensive Location Heuristic Mapping Dictionary (State/City -> Lat/Lon)
INDIAN_LOCATIONS = {
    # States & Union Territories (Capital Coordinates)
    "WEST BENGAL": {"state": "West Bengal", "city": "Kolkata", "lat": 22.5726, "lon": 88.3639},
    "TAMIL NADU": {"state": "Tamil Nadu", "city": "Chennai", "lat": 13.0827, "lon": 80.2707},
    "MAHARASHTRA": {"state": "Maharashtra", "city": "Mumbai", "lat": 19.0760, "lon": 72.8777},
    "DELHI": {"state": "Delhi", "city": "Delhi", "lat": 28.6139, "lon": 77.2090},
    "KARNATAKA": {"state": "Karnataka", "city": "Bengaluru", "lat": 12.9716, "lon": 77.5946},
    "GUJARAT": {"state": "Gujarat", "city": "Ahmedabad", "lat": 23.0225, "lon": 72.5714},
    "RAJASTHAN": {"state": "Rajasthan", "city": "Jaipur", "lat": 26.9124, "lon": 75.7873},
    "TELANGANA": {"state": "Telangana", "city": "Hyderabad", "lat": 17.3850, "lon": 78.4867},
    "MADHYA PRADESH": {"state": "Madhya Pradesh", "city": "Bhopal", "lat": 23.2599, "lon": 77.4126},
    "UTTAR PRADESH": {"state": "Uttar Pradesh", "city": "Lucknow", "lat": 26.8467, "lon": 80.9462},
    "KERALA": {"state": "Kerala", "city": "Thiruvananthapuram", "lat": 8.5241, "lon": 76.9366},
    "ODISHA": {"state": "Odisha", "city": "Bhubaneswar", "lat": 20.2961, "lon": 85.8245},
    "ANDHRA PRADESH": {"state": "Andhra Pradesh", "city": "Visakhapatnam", "lat": 17.6868, "lon": 83.2185},
    "ASSAM": {"state": "Assam", "city": "Guwahati", "lat": 26.1445, "lon": 91.7362},
    "BIHAR": {"state": "Bihar", "city": "Patna", "lat": 25.5941, "lon": 85.1376},
    "PUNJAB": {"state": "Punjab", "city": "Chandigarh", "lat": 30.7333, "lon": 76.7794},
    "HARYANA": {"state": "Haryana", "city": "Gurugram", "lat": 28.4595, "lon": 77.0266},
    "JHARKHAND": {"state": "Jharkhand", "city": "Ranchi", "lat": 23.3441, "lon": 85.3096},
    "CHHATTISGARH": {"state": "Chhattisgarh", "city": "Raipur", "lat": 21.2514, "lon": 81.6296},
    "HIMACHAL PRADESH": {"state": "Himachal Pradesh", "city": "Shimla", "lat": 31.1048, "lon": 77.1734},
    "UTTARAKHAND": {"state": "Uttarakhand", "city": "Dehradun", "lat": 30.3165, "lon": 78.0322},
    "JAMMU AND KASHMIR": {"state": "Jammu and Kashmir", "city": "Srinagar", "lat": 34.0837, "lon": 74.7973},
    "GOA": {"state": "Goa", "city": "Panaji", "lat": 15.4989, "lon": 73.8278},
    "SIKKIM": {"state": "Sikkim", "city": "Gangtok", "lat": 27.3389, "lon": 88.6065},
    "TRIPURA": {"state": "Tripura", "city": "Agartala", "lat": 23.8315, "lon": 91.2868},
    "MEGHALAYA": {"state": "Meghalaya", "city": "Shillong", "lat": 25.5788, "lon": 91.8933},
    "MANIPUR": {"state": "Manipur", "city": "Imphal", "lat": 24.8170, "lon": 93.9368},
    "NAGALAND": {"state": "Nagaland", "city": "Kohima", "lat": 25.6751, "lon": 94.1086},
    "ARUNACHAL PRADESH": {"state": "Arunachal Pradesh", "city": "Itanagar", "lat": 27.0844, "lon": 93.6053},
    "MIZORAM": {"state": "Mizoram", "city": "Aizawl", "lat": 23.7271, "lon": 92.7176},
    "DADRA AND NAGAR HAVELI": {"state": "Dadra and Nagar Haveli", "city": "Silvassa", "lat": 20.2763, "lon": 73.0083},
    "DAMAN": {"state": "Daman and Diu", "city": "Daman", "lat": 20.4283, "lon": 72.8397},
    "PUDUCHERRY": {"state": "Puducherry", "city": "Puducherry", "lat": 11.9416, "lon": 79.8083},

    # Key Districts & Cities
    "KOLKATA": {"state": "West Bengal", "city": "Kolkata", "lat": 22.5726, "lon": 88.3639},
    "CHENNAI": {"state": "Tamil Nadu", "city": "Chennai", "lat": 13.0827, "lon": 80.2707},
    "MUMBAI": {"state": "Maharashtra", "city": "Mumbai", "lat": 19.0760, "lon": 72.8777},
    "BENGALURU": {"state": "Karnataka", "city": "Bengaluru", "lat": 12.9716, "lon": 77.5946},
    "HYDERABAD": {"state": "Telangana", "city": "Hyderabad", "lat": 17.3850, "lon": 78.4867},
    "AHMEDABAD": {"state": "Gujarat", "city": "Ahmedabad", "lat": 23.0225, "lon": 72.5714},
    "JAIPUR": {"state": "Rajasthan", "city": "Jaipur", "lat": 26.9124, "lon": 75.7873},
    "LUCKNOW": {"state": "Uttar Pradesh", "city": "Lucknow", "lat": 26.8467, "lon": 80.9462},
    "BHOPAL": {"state": "Madhya Pradesh", "city": "Bhopal", "lat": 23.2599, "lon": 77.4126},
    "MADURAI": {"state": "Tamil Nadu", "city": "Madurai", "lat": 9.9252, "lon": 78.1198},
    "KOCHI": {"state": "Kerala", "city": "Kochi", "lat": 9.9312, "lon": 76.2673},
    "PUNE": {"state": "Maharashtra", "city": "Pune", "lat": 18.5204, "lon": 73.8567},
    "DARJEELING": {"state": "West Bengal", "city": "Darjeeling", "lat": 27.0410, "lon": 88.2663},
    "GANGTOK": {"state": "Sikkim", "city": "Gangtok", "lat": 27.3389, "lon": 88.6065},
    "BANKURA": {"state": "West Bengal", "city": "Bankura", "lat": 23.2324, "lon": 87.0716},
    "PURULIA": {"state": "West Bengal", "city": "Purulia", "lat": 23.3323, "lon": 86.3653},
    "SURAT": {"state": "Gujarat", "city": "Surat", "lat": 21.1702, "lon": 72.8311},
    "VADODARA": {"state": "Gujarat", "city": "Vadodara", "lat": 22.3072, "lon": 73.1812},
    "VISAKHAPATNAM": {"state": "Andhra Pradesh", "city": "Visakhapatnam", "lat": 17.6868, "lon": 83.2185},
    "COIMBATORE": {"state": "Tamil Nadu", "city": "Coimbatore", "lat": 11.0168, "lon": 76.9558}
}


def parse_location_info(author_text, title_text, area_desc):
    """
    Extract state, city, latitude, and longitude from SACHET RSS text fields using keyword matching.
    """
    combined_text = f"{author_text or ''} {title_text or ''} {area_desc or ''}".upper()

    matched_loc = None
    for loc_key, loc_info in INDIAN_LOCATIONS.items():
        if loc_key in combined_text:
            matched_loc = loc_info
            # Prefer city-level matches over state-level matches if available
            if loc_info["city"].upper() in loc_key:
                break

    if matched_loc:
        return matched_loc["state"], matched_loc["city"], matched_loc["lat"], matched_loc["lon"]

    # Fallback parsing for author, e.g. "controlroom@ndma.gov.in (IMD Kolkata)"
    if author_text and "(" in author_text:
        source_name = author_text.split("(")[-1].replace(")", "").strip()
        parts = source_name.split()
        if len(parts) > 1:
            possible_city = parts[-1].upper()
            if possible_city in INDIAN_LOCATIONS:
                loc = INDIAN_LOCATIONS[possible_city]
                return loc["state"], loc["city"], loc["lat"], loc["lon"]
            return "India", parts[-1].title(), None, None

    return "India", "National", None, None


def map_sachet_event_type(raw_event, title_text):
    """
    Map raw SACHET event / title string to standardized platform event categories.
    """
    text = f"{raw_event or ''} {title_text or ''}".lower()

    if any(k in text for k in ["flood", "inundat", "overflow"]):
        return "Flood Risk"
    elif any(k in text for k in ["heavy rain", "torrential", "downpour", "intense rain"]):
        return "Heavy Rainfall"
    elif any(k in text for k in ["thunderstorm", "lightning", "thunder", "ts"]):
        return "Thunderstorm"
    elif any(k in text for k in ["cyclone", "gale", "squall", "storm"]):
        return "Strong Wind"
    elif any(k in text for k in ["heatwave", "heat wave", "hot"]):
        return "Heatwave"
    elif any(k in text for k in ["fog", "mist", "haze", "smog", "visibility"]):
        return "Fog / Low Visibility"
    elif any(k in text for k in ["dust", "sandstorm"]):
        return "Dust Storm"
    elif "rain" in text:
        return "Heavy Rainfall"
    elif "wind" in text:
        return "Strong Wind"
    
    return raw_event if raw_event else "Severe Weather"


def map_sachet_severity(raw_severity):
    """
    Map SACHET/CAP severity rating to system standard HIGH, MEDIUM, LOW.
    """
    if not raw_severity:
        return "MEDIUM"
    
    sev = str(raw_severity).strip().upper()
    if sev in ["EXTREME", "SEVERE"]:
        return "HIGH"
    elif sev in ["MODERATE"]:
        return "MEDIUM"
    elif sev in ["MINOR", "UNKNOWN"]:
        return "LOW"
    
    return "MEDIUM"


def parse_pubdate(date_str):
    """
    Parse RFC 822 pubDate string (e.g. 'Thu, 17 Sep 2026 13:41:02 GMT') to datetime string.
    """
    if not date_str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        dt = parsedate_to_datetime(date_str)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def fetch_cap_xml_details(link_url):
    """
    Fetch and parse detailed CAP XML file from SACHET link URL.
    Returns dictionary of CAP metadata attributes or empty dict on failure.
    """
    if not link_url or not link_url.startswith("http"):
        return {}

    try:
        resp = requests.get(link_url, timeout=8, verify=False)
        if resp.status_code == 200:
            root = ET.fromstring(resp.content)
            info = root.find("cap:info", CAP_NS)
            if info is not None:
                def get_tag(tag_name):
                    el = info.find(f"cap:{tag_name}", CAP_NS)
                    return el.text.strip() if el is not None and el.text else ""

                area_desc = ""
                area = info.find(".//cap:area", CAP_NS)
                if area is not None:
                    area_desc_el = area.find("cap:areaDesc", CAP_NS)
                    if area_desc_el is not None and area_desc_el.text:
                        area_desc = area_desc_el.text.strip()

                return {
                    "event": get_tag("event"),
                    "severity": get_tag("severity"),
                    "urgency": get_tag("urgency"),
                    "certainty": get_tag("certainty"),
                    "headline": get_tag("headline"),
                    "description": get_tag("description"),
                    "instruction": get_tag("instruction"),
                    "area_desc": area_desc
                }
    except Exception as e:
        logger.debug("Failed to fetch/parse CAP XML details from %s: %s", link_url, str(e))

    return {}


def fetch_sachet_rss():
    """
    Fetch official SACHET/NDMA RSS feed using HTTP conditional requests (ETag/Last-Modified).
    Parses RSS XML items and fetches detailed CAP metadata for each item.
    Returns list of parsed alert dictionaries.
    """
    global _LAST_ETAG, _LAST_MODIFIED

    headers = {
        "User-Agent": "NationalWeatherPlatform/2.0 (Disaster Alert Monitor)"
    }
    if _LAST_ETAG:
        headers["If-None-Match"] = _LAST_ETAG
    if _LAST_MODIFIED:
        headers["If-Modified-Since"] = _LAST_MODIFIED

    try:
        response = requests.get(SACHET_RSS_URL, headers=headers, timeout=12, verify=False)

        if response.status_code == 304:
            logger.info("SACHET RSS feed not modified since last check (304 Not Modified).")
            return []

        if response.status_code != 200:
            logger.warning("SACHET RSS returned HTTP status %d", response.status_code)
            return []

        # Update cache headers
        _LAST_ETAG = response.headers.get("ETag")
        _LAST_MODIFIED = response.headers.get("Last-Modified")

        root = ET.fromstring(response.content)
        items = root.findall(".//item")
        logger.info("Fetched SACHET RSS feed successfully (%d alert items found).", len(items))

        parsed_alerts = []

        for item in items:
            title = item.findtext("title", "").strip()
            link = item.findtext("link", "").strip()
            author = item.findtext("author", "").strip()
            guid = item.findtext("guid", "").strip() or link
            pub_date_raw = item.findtext("pubDate", "").strip()
            pub_datetime = parse_pubdate(pub_date_raw)

            # Fetch detailed CAP attributes from item XML link
            cap_details = fetch_cap_xml_details(link)

            raw_event = cap_details.get("event") or title.split(".")[0]
            raw_sev = cap_details.get("severity") or "Moderate"
            area_desc = cap_details.get("area_desc") or ""

            event_type = map_sachet_event_type(raw_event, title)
            severity = map_sachet_severity(raw_sev)
            state, city, lat, lon = parse_location_info(author, title, area_desc)

            description = cap_details.get("headline") or cap_details.get("description") or title
            instruction = cap_details.get("instruction") or "Follow State Disaster Management Authority guidelines."

            alert_dict = {
                "guid": guid,
                "link": link,
                "title": title,
                "description": description,
                "instruction": instruction,
                "source": "SACHET / NDMA",
                "publisher": author or "NDMA / IMD Control Room",
                "event_type": event_type,
                "severity": severity,
                "city": city,
                "state": state,
                "latitude": lat,
                "longitude": lon,
                "event_confidence": 95.0,  # Official government source high confidence
                "status": "Active",
                "detected_at": pub_datetime
            }
            parsed_alerts.append(alert_dict)

        return parsed_alerts

    except requests.exceptions.Timeout:
        logger.error("Timeout fetching SACHET RSS feed from %s", SACHET_RSS_URL)
        return []
    except requests.exceptions.RequestException as e:
        logger.error("Network error connecting to SACHET RSS feed: %s", str(e))
        return []
    except ET.ParseError as e:
        logger.error("XML parse error processing SACHET RSS feed: %s", str(e))
        return []
    except Exception as e:
        logger.error("Unexpected error in SACHET ingestion: %s", str(e))
        return []


def fetch_and_store_sachet_alerts():
    """
    Complete ingestion cycle for SACHET RSS disaster alerts.
    Fetches RSS feed items, checks PostgreSQL database for duplicates via guid/link,
    and inserts new alerts into weather_alerts table.
    Returns (imported_count, skipped_count, total_fetched)
    """
    alerts = fetch_sachet_rss()
    if not alerts:
        return 0, 0, 0

    try:
        from database.db import insert_sachet_alerts_to_db
        imported, skipped = insert_sachet_alerts_to_db(alerts)
        logger.info("SACHET RSS Ingestion complete: %d new inserted, %d skipped as duplicate.", imported, skipped)
        return imported, skipped, len(alerts)
    except Exception as e:
        logger.error("Error saving SACHET alerts to PostgreSQL database: %s", str(e))
        return 0, 0, len(alerts)
