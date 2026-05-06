"""Splunk REST API client for detection management."""
import requests
import urllib3
from typing import Optional, Dict, Any

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class SplunkClient:
    def __init__(
        self,
        base_url: str,
        token: str = None,
        username: str = None,
        password: str = None,
        verify_ssl: bool = False,
    ):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.verify = verify_ssl

        if token:
            self.session.headers["Authorization"] = f"Bearer {token}"
        elif username and password:
            self.session.auth = (username, password)
        else:
            raise ValueError("Provide either token or username+password")

    def validate_spl(self, search: str) -> Dict[str, Any]:
        """Use Splunk's parser endpoint to check SPL syntax."""
        resp = self.session.post(
            f"{self.base_url}/services/search/parser",
            data={"q": f"search {search}", "output_mode": "json"},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def get_saved_search(
        self, name: str, app: str = "search", owner: str = "nobody"
    ) -> Optional[Dict]:
        encoded = requests.utils.quote(name, safe="")
        resp = self.session.get(
            f"{self.base_url}/servicesNS/{owner}/{app}/saved/searches/{encoded}",
            params={"output_mode": "json"},
            timeout=30,
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()

    def create_saved_search(
        self,
        name: str,
        search: str,
        params: Dict,
        app: str = "search",
        owner: str = "nobody",
    ) -> Dict:
        data = {"name": name, "search": search, **params, "output_mode": "json"}
        resp = self.session.post(
            f"{self.base_url}/servicesNS/{owner}/{app}/saved/searches",
            data=data,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def update_saved_search(
        self,
        name: str,
        search: str,
        params: Dict,
        app: str = "search",
        owner: str = "nobody",
    ) -> Dict:
        encoded = requests.utils.quote(name, safe="")
        data = {"search": search, **params, "output_mode": "json"}
        resp = self.session.post(
            f"{self.base_url}/servicesNS/{owner}/{app}/saved/searches/{encoded}",
            data=data,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def delete_saved_search(
        self, name: str, app: str = "search", owner: str = "nobody"
    ) -> bool:
        encoded = requests.utils.quote(name, safe="")
        resp = self.session.delete(
            f"{self.base_url}/servicesNS/{owner}/{app}/saved/searches/{encoded}",
            timeout=30,
        )
        return resp.status_code == 200

    def health_check(self) -> bool:
        try:
            resp = self.session.get(
                f"{self.base_url}/services/server/info",
                params={"output_mode": "json"},
                timeout=10,
            )
            return resp.status_code == 200
        except Exception:
            return False
