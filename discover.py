"""Run this once to discover which OwnerRez API endpoints are available."""
import os
import requests
from dotenv import load_dotenv

load_dotenv()
auth = (os.getenv("OWNERREZ_EMAIL"), os.getenv("OWNERREZ_TOKEN"))
headers = {"Accept": "application/json", "User-Agent": "VRMV-Agent/1.0"}
base = "https://api.ownerrez.com/v2"

candidates = [
    "triggers", "triggerrules", "emailtriggers", "messagetriggers",
    "smstriggers", "notifications", "automations", "rules",
    "messagetemplates", "emailtemplates", "templates", "messages",
    "properties", "bookings", "guests", "channels", "listings",
    "rates", "fees", "taxes", "photos", "reviews", "inquiries",
]

print(f"Probing {base}...\n")
for ep in candidates:
    r = requests.get(f"{base}/{ep}?limit=1", auth=auth, headers=headers)
    print(f"  {ep:25s} -> {r.status_code}")
