"""
OwnerRez API client — handles auth, pagination, and all GET/POST/PATCH calls.
"""

import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://api.ownerrez.com/v2"
HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "User-Agent": "VRMV-Agent/1.0",
}


class OwnerRezClient:
    def __init__(self):
        email = os.getenv("OWNERREZ_EMAIL")
        token = os.getenv("OWNERREZ_TOKEN")
        if not email or not token:
            raise ValueError(
                "OWNERREZ_EMAIL and OWNERREZ_TOKEN must be set in .env"
            )
        self.auth = (email, token)
        self.session = requests.Session()
        self.session.auth = self.auth
        self.session.headers.update(HEADERS)

    def _request(self, method, path, **kwargs):
        url = f"{BASE_URL}{path}"
        resp = self.session.request(method, url, **kwargs)
        if resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", 5))
            print(f"  Rate limited — waiting {retry_after}s...")
            time.sleep(retry_after)
            resp = self.session.request(method, url, **kwargs)
        resp.raise_for_status()
        return resp.json() if resp.content else {}

    def _get_paged(self, path, params=None):
        """Fetch all pages from a paged endpoint, return combined items list."""
        params = dict(params or {})
        params.setdefault("limit", 100)
        params["skip"] = 0
        results = []
        while True:
            data = self._request("GET", path, params=params)
            # OwnerRez returns {"items": [...], "total_count": N} or just a list
            if isinstance(data, list):
                results.extend(data)
                break
            items = data.get("items", data.get("results", []))
            results.extend(items)
            total = data.get("total_count", data.get("total", len(results)))
            params["skip"] += len(items)
            if params["skip"] >= total or not items:
                break
        return results

    # --- Read endpoints ---

    def get_properties(self):
        return self._get_paged("/properties")

    def get_triggers(self):
        return self._get_paged("/triggers")

    def get_templates(self):
        return self._get_paged("/messagetemplates")

    def get_property(self, property_id):
        return self._request("GET", f"/properties/{property_id}")

    def get_trigger(self, trigger_id):
        return self._request("GET", f"/triggers/{trigger_id}")

    def get_template(self, template_id):
        return self._request("GET", f"/messagetemplates/{template_id}")

    def get_field_defs(self):
        """Fetch available field definitions to understand door lock / deposit fields."""
        try:
            return self._request("GET", "/fielddefs")
        except Exception:
            return {}

    # --- Write endpoints (Phase 2) ---

    def create_trigger(self, payload: dict):
        return self._request("POST", "/triggers", json=payload)

    def update_trigger(self, trigger_id, payload: dict):
        return self._request("PATCH", f"/triggers/{trigger_id}", json=payload)

    def create_template(self, payload: dict):
        return self._request("POST", "/messagetemplates", json=payload)

    def update_template(self, template_id, payload: dict):
        return self._request("PATCH", f"/messagetemplates/{template_id}", json=payload)

    def update_property(self, property_id, payload: dict):
        return self._request("PATCH", f"/properties/{property_id}", json=payload)

    def test_connection(self):
        """Verify credentials by hitting /properties and returning basic info."""
        data = self._request("GET", "/properties", params={"limit": 1})
        return data
