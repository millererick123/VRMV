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

TRIGGER_CANDIDATES = ["triggers", "triggerrules", "emailtriggers", "messagetriggers"]
TEMPLATE_CANDIDATES = ["messagetemplates", "templates", "emailtemplates", "messagetemplate"]


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
        self._endpoint_cache = {}

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

    def _probe(self, path):
        """Return True if the endpoint returns 200, False otherwise."""
        url = f"{BASE_URL}{path}"
        try:
            resp = self.session.get(url, params={"limit": 1})
            return resp.status_code == 200
        except Exception:
            return False

    def _discover_endpoint(self, resource_key, candidates):
        if resource_key in self._endpoint_cache:
            return self._endpoint_cache[resource_key]
        for name in candidates:
            path = f"/{name}"
            if self._probe(path):
                self._endpoint_cache[resource_key] = path
                return path
        self._endpoint_cache[resource_key] = f"/{candidates[0]}"
        return self._endpoint_cache[resource_key]

    @property
    def _triggers_path(self):
        return self._discover_endpoint("triggers", TRIGGER_CANDIDATES)

    @property
    def _templates_path(self):
        return self._discover_endpoint("templates", TEMPLATE_CANDIDATES)

    def _get_paged(self, path, params=None):
        params = dict(params or {})
        params.setdefault("limit", 100)
        params["skip"] = 0
        results = []
        while True:
            data = self._request("GET", path, params=params)
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

    def get_properties(self):
        return self._get_paged("/properties")

    def get_triggers(self):
        return self._get_paged(self._triggers_path)

    def get_templates(self):
        return self._get_paged(self._templates_path)

    def get_property(self, property_id):
        return self._request("GET", f"/properties/{property_id}")

    def get_trigger(self, trigger_id):
        return self._request("GET", f"{self._triggers_path}/{trigger_id}")

    def get_template(self, template_id):
        return self._request("GET", f"{self._templates_path}/{template_id}")

    def get_bookings(self, params=None):
        return self._get_paged("/bookings", params=params)

    def get_guests(self, params=None):
        return self._get_paged("/guests", params=params)

    def get_channels(self, params=None):
        return self._get_paged("/channels", params=params)

    def get_fees(self, params=None):
        return self._get_paged("/fees", params=params)

    def get_taxes(self, params=None):
        return self._get_paged("/taxes", params=params)

    def get_field_defs(self):
        try:
            return self._request("GET", "/fielddefs")
        except Exception:
            return {}

    def create_trigger(self, payload: dict):
        return self._request("POST", self._triggers_path, json=payload)

    def update_trigger(self, trigger_id, payload: dict):
        return self._request("PATCH", f"{self._triggers_path}/{trigger_id}", json=payload)

    def create_template(self, payload: dict):
        return self._request("POST", self._templates_path, json=payload)

    def update_template(self, template_id, payload: dict):
        return self._request("PATCH", f"{self._templates_path}/{template_id}", json=payload)

    def update_property(self, property_id, payload: dict):
        return self._request("PATCH", f"/properties/{property_id}", json=payload)

    def test_connection(self):
        data = self._request("GET", "/properties", params={"limit": 1})
        return data
