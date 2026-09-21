import requests
import xml.etree.ElementTree as ET


URL = "https://sachet.ndma.gov.in/cap_public_website/rss/rss_india.xml"


response = requests.get(URL, timeout=20)

print("Status:", response.status_code)

root = ET.fromstring(response.content)

items = root.findall(".//item")

print("Number of alerts:", len(items))

for i, item in enumerate(items[:5], start=1):

    print("\n============================")
    print("ALERT", i)
    print("============================")

    for child in item:
        print(child.tag, "=>", child.text)