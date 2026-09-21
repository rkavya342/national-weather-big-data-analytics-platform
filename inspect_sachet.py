import requests
import xml.etree.ElementTree as ET

url = "https://sachet.ndma.gov.in/cap_public_website/rss/rss_india.xml"

response = requests.get(url, timeout=30)
response.raise_for_status()

root = ET.fromstring(response.content)

# Get the first alert
item = root.find(".//item")

if item is not None:
    print("\n===== FIRST SACHET ALERT =====\n")

    for element in item:
        print("TAG :", element.tag)
        print("VALUE:", element.text)
        print("-" * 60)
else:
    print("No alerts found.")