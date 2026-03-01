import requests
import os
import json
from datetime import datetime
import time


class MeegleClient:
    def __init__(self):
        self.domain = os.getenv("MEEGLE_DOMAIN")
        self.plugin_id = os.getenv("MEEGLE_PLUGIN_ID")
        self.plugin_secret = os.getenv("MEEGLE_PLUGIN_SECRET")
        self.project_key = os.getenv("MEEGLE_PROJECT_KEY")
        self.external_project_key = os.getenv("MEEGLE_EXTERNAL_PROJECT_KEY")
        self.user_key = os.getenv("MEEGLE_USER_KEY")

        self.base_url = f"https://{self.domain}"
        self.bff_url = f"https://{self.domain}/bff/v2"
        self.api_url = f"https://{self.domain}/open_api"

        self.access_token = None
        self.token_expiry = 0

        if not self.user_key:
            print(f"WARNING: MEEGLE_USER_KEY not set! This is REQUIRED for API calls.")

        print(f"DEBUG: Meegle domain: {self.domain}")
        print(f"DEBUG: Meegle project key: {self.project_key}")
        print(f"DEBUG: Meegle external project key: {self.external_project_key}")
        print(f"DEBUG: User key: {self.user_key[:10]}..." if self.user_key else "DEBUG: No User Key")
        print(f"DEBUG: Plugin ID: {self.plugin_id[:10]}..." if self.plugin_id else "DEBUG: No Plugin ID")

    def get_access_token(self):
        """Get or refresh access token using plugin ID and secret"""
        print("DEBUG: get_access_token VERSION 2.1 - FIXED TOKEN PARSING")

        if self.access_token and time.time() < self.token_expiry:
            print(f"DEBUG: Using cached token: {self.access_token[:20]}...")
            return self.access_token

        url = f"{self.bff_url}/authen/plugin_token"
        payload = {
            "plugin_id": self.plugin_id,
            "plugin_secret": self.plugin_secret
        }
        headers = {"Content-Type": "application/json"}

        print(f"DEBUG: Requesting Meegle access token from {url}")

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            response.raise_for_status()

            data = response.json()
            print(f"DEBUG: Full token response: {json.dumps(data, indent=2)}")

            error_data = data.get("error", {})
            if error_data.get("code", 0) != 0:
                error_msg = error_data.get("msg", "Unknown error")
                raise Exception(f"Meegle auth error: {error_msg}")

            token_data = data.get("data", {})
            self.access_token = token_data.get("token")
            expires_in = token_data.get("expire_time", 7200)
            self.token_expiry = time.time() + expires_in - 300

            print(f"DEBUG: Extracted token: {self.access_token}")
            print(f"DEBUG: Token first 20 chars: {self.access_token[:20] if self.access_token else 'None'}...")
            print(f"DEBUG: Expires in: {expires_in}s")

            if not self.access_token:
                raise Exception("Failed to extract token from response")

            return self.access_token

        except requests.exceptions.RequestException as e:
            print(f"ERROR: Meegle token request failed: {e}")
            raise

    def _get_headers(self):
        """Build request headers with token"""
        token = self.get_access_token()
        headers = {
            "Content-Type": "application/json",
            "X-PLUGIN-TOKEN": token,
            "X-USER-KEY": self.user_key
        }
        print(f"DEBUG: Request headers: X-PLUGIN-TOKEN={token[:20] if token else 'None'}..., X-USER-KEY={self.user_key}")
        return headers

    def get_all_work_items(self, project_key, type_key="story", page_size=100):
        """
        ✅ NEW: Fetch ALL work items for a project using pagination.
        Loops through pages until no more items are returned.

        Args:
            project_key: Meegle project key (SearchArb or External)
            type_key: Work item type (default "story")
            page_size: Items per page (max 100)

        Returns:
            Dict with {"data": [all items combined]}
        """
        url = f"{self.api_url}/{project_key}/work_item/filter"
        all_items = []
        page_num = 1

        print(f"DEBUG: Fetching ALL items from project {project_key}")

        while True:
            payload = {
                "page_size": page_size,
                "page_num": page_num,
                "work_item_type_keys": [type_key]
            }

            print(f"DEBUG: Meegle API request URL: {url}")
            print(f"DEBUG: Meegle API request payload: {payload}")

            try:
                response = requests.post(
                    url,
                    headers=self._get_headers(),
                    json=payload,
                    timeout=30
                )

                print(f"DEBUG: Meegle API response status: {response.status_code}")

                response.raise_for_status()
                data = response.json()

                if data.get("err_code", 0) != 0:
                    error_msg = data.get("err_msg", "Unknown error")
                    print(f"ERROR: Meegle API error: {error_msg}")
                    raise Exception(f"Meegle API error: {error_msg}")

                page_items = data.get("data", [])
                print(f"DEBUG: Page {page_num} returned {len(page_items)} items")

                if not page_items:
                    # No more items - done paginating
                    print(f"DEBUG: Pagination complete. Total items: {len(all_items)}")
                    break

                all_items.extend(page_items)

                if len(page_items) < page_size:
                    # Last page - fewer items than page_size means no more pages
                    print(f"DEBUG: Last page reached. Total items: {len(all_items)}")
                    break

                page_num += 1

            except requests.exceptions.RequestException as e:
                print(f"ERROR: Meegle API request failed on page {page_num}: {e}")
                raise

        return {"data": all_items}

    def search_work_items(self, filters=None):
        """
        Search work items. If filters contains project_key, use that.
        Otherwise fall back to default project key from .env.
        Supports pagination automatically via get_all_work_items().

        Args:
            filters: Dict optionally containing:
                - project_key: override default project
                - type_key: work item type (default "story")
        """
        project_key = self.project_key  # default from .env
        type_key = "story"

        if filters:
            project_key = filters.get("project_key", project_key)
            type_key = filters.get("type_key", type_key)

        print(f"DEBUG: search_work_items using project_key={project_key}, type_key={type_key}")

        return self.get_all_work_items(project_key, type_key)

    def test_connection(self):
        """Test API connection"""
        try:
            result = self.get_all_work_items(self.project_key, page_size=10)
            return result
        except Exception as e:
            raise
