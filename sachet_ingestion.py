import requests
import xml.etree.ElementTree as ET
from datetime import datetime
from database import get_db_connection


SACHET_RSS_URL = "https://sachet.ndma.gov.in/cap_public_website/rss/rss_india.xml"


def fetch_sachet_alerts():
    try:
        response = requests.get(
            SACHET_RSS_URL,
            timeout=20
        )

        response.raise_for_status()

        root = ET.fromstring(response.content)

        alerts = []

        for item in root.findall(".//item"):
            title = item.findtext("title", default="").strip()
            description = item.findtext("description", default="").strip()
            link = item.findtext("link", default="").strip()
            pub_date = item.findtext("pubDate", default="").strip()

            alerts.append({
                "title": title,
                "description": description,
                "link": link,
                "pub_date": pub_date,
                "source": "SACHET"
            })

        print(f"SACHET: Found {len(alerts)} alerts")

        return True, alerts

    except Exception as e:
        print(f"SACHET ingestion error: {e}")
        return False, str(e)