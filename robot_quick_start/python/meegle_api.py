import requests
import os
from datetime import datetime
import time

class MeegleClient:
    def __init__(self):
        self.domain = os.getenv("MEEGLE_DOMAIN")
        self.plugin_id = os.getenv("MEEGLE_PLUGIN_ID")
        self.plugin_secret = os.getenv("MEEGLE_PLUGIN_SECRET")
        self.project_key = os.getenv("MEEGLE_PROJECT_KEY")
        self.base_url = f"https://{self.domain}/open_api"
        
        self.access_token = None
        self.token_expiry = 0
        
        print(f"DEBUG: Meegle domain: {self.domain}")
        print(f"DEBUG: Meegle project key: {self.project_key}")
        print(f"DEBUG: Plugin ID: {self.plugin_id[:10]}..." if self.plugin_id else "DEBUG: No Plugin ID")
    
    def get_access_token(self):
        """Get or refresh access token using plugin ID and secret"""
        # Return cached token if still valid
        if self.access_token and time.time() < self.token_expiry:
            return self.access_token
        
        # Get new token
        url = f"https://{self.domain}/open_api/authen/plugin_token"
        
        payload = {
            "plugin_id": self.plugin_id,
            "plugin_secret": self.plugin_secret
        }
        
        headers = {
            "Content-Type": "application/json"
        }
        
        print(f"DEBUG: Requesting Meegle access token...")
        
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get("err_code", 0) != 0:
                error_msg = data.get("err_msg", "Unknown error")
                print(f"ERROR: Failed to get Meegle token: {error_msg}")
                raise Exception(f"Meegle auth error: {error_msg}")
            
            self.access_token = data.get("plugin_token")
            expires_in = data.get("expire", 7200)  # Default 2 hours
            self.token_expiry = time.time() + expires_in - 300  # Refresh 5 min early
            
            print(f"DEBUG: Got Meegle token, expires in {expires_in}s")
            
            return self.access_token
            
        except requests.exceptions.RequestException as e:
            print(f"ERROR: Meegle token request failed: {e}")
            raise
    
    def _get_headers(self, idempotent_uuid=None):
        """Build request headers with token"""
        token = self.get_access_token()
        
        headers = {
            "Content-Type": "application/json",
            "X-PLUGIN-TOKEN": token
        }
        
        if idempotent_uuid:
            headers["X-IDEM-UUID"] = idempotent_uuid
        
        return headers
    
    def search_work_items(self, filters=None):
        """
        Search for work items in the project
        
        Args:
            filters: Dict with filter criteria
                - assignee: User name or ID
                - status: Status name
                - start_date: ISO format date string
                - end_date: ISO format date string
                - language: Language value
        """
        url = f"{self.base_url}/{self.project_key}/work_items/search"
        
        payload = {}
        
        if filters:
            if "assignee" in filters:
                payload["assignee"] = filters["assignee"]
            if "status" in filters:
                payload["status"] = filters["status"]
            if "start_date" in filters and "end_date" in filters:
                payload["date_range"] = {
                    "start": filters["start_date"],
                    "end": filters["end_date"]
                }
            if "language" in filters:
                payload["custom_fields"] = {
                    "language": filters["language"]
                }
        
        print(f"DEBUG: Meegle API request URL: {url}")
        print(f"DEBUG: Meegle API request payload: {payload}")
        
        try:
            response = requests.post(
                url,
                headers=self._get_headers(),
                json=payload,
                timeout=10
            )
            
            print(f"DEBUG: Meegle API response status: {response.status_code}")
            print(f"DEBUG: Meegle API response: {response.text[:500]}")
            
            response.raise_for_status()
            data = response.json()
            
            if data.get("err_code", 0) != 0:
                error_msg = data.get("err_msg", "Unknown error")
                print(f"ERROR: Meegle API error: {error_msg}")
                raise Exception(f"Meegle API error: {error_msg}")
            
            return data
            
        except requests.exceptions.RequestException as e:
            print(f"ERROR: Meegle API request failed: {e}")
            raise
    
    def get_all_work_items(self):
        """Get all work items from the project (for testing)"""
        url = f"{self.base_url}/{self.project_key}/business/all"
        
        try:
            response = requests.get(
                url,
                headers=self._get_headers(),
                timeout=10
            )
            
            print(f"DEBUG: Get all items response: {response.status_code}")
            
            response.raise_for_status()
            data = response.json()
            
            if data.get("err_code", 0) != 0:
                error_msg = data.get("err_msg", "Unknown error")
                raise Exception(f"Meegle API error: {error_msg}")
            
            return data
            
        except requests.exceptions.RequestException as e:
            print(f"ERROR: Meegle API request failed: {e}")
            raise
    
    def search_user(self, name):
        """Find user by name"""
        url = f"{self.base_url}/{self.project_key}/users/search"
        
        payload = {"name": name}
        
        try:
            response = requests.post(
                url,
                headers=self._get_headers(),
                json=payload,
                timeout=10
            )
            
            response.raise_for_status()
            data = response.json()
            
            if data.get("err_code", 0) != 0:
                return None
            
            users = data.get("users", [])
            return users[0] if users else None
            
        except requests.exceptions.RequestException as e:
            print(f"ERROR: User search failed: {e}")
            return None

