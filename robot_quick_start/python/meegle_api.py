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
        self.user_key = os.getenv("MEEGLE_USER_KEY")  # REQUIRED - not optional!
        
        # Corrected base URLs
        self.base_url = f"https://{self.domain}"
        self.bff_url = f"https://{self.domain}/bff/v2"
        self.api_url = f"https://{self.domain}/open_api"
        
        self.access_token = None
        self.token_expiry = 0
        
        if not self.user_key:
            print(f"WARNING: MEEGLE_USER_KEY not set! This is REQUIRED for API calls.")
        
        print(f"DEBUG: Meegle domain: {self.domain}")
        print(f"DEBUG: Meegle project key: {self.project_key}")
        print(f"DEBUG: User key: {self.user_key[:10]}..." if self.user_key else "DEBUG: No User Key")
        print(f"DEBUG: Plugin ID: {self.plugin_id[:10]}..." if self.plugin_id else "DEBUG: No Plugin ID")
    
    def get_access_token(self):
        """Get or refresh access token using plugin ID and secret"""
        # Return cached token if still valid
        if self.access_token and time.time() < self.token_expiry:
            return self.access_token
        
        # Get new token - CORRECTED ENDPOINT
        url = f"{self.bff_url}/authen/plugin_token"
        
        payload = {
            "plugin_id": self.plugin_id,
            "plugin_secret": self.plugin_secret
        }
        
        headers = {
            "Content-Type": "application/json"
        }
        
        print(f"DEBUG: Requesting Meegle access token from {url}")
        
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            # DEBUG: Print full response
            print(f"DEBUG: Full token response: {json.dumps(data, indent=2)}")
            
            if data.get("err_code", 0) != 0:
                error_msg = data.get("err_msg", "Unknown error")
                print(f"ERROR: Failed to get Meegle token: {error_msg}")
                raise Exception(f"Meegle auth error: {error_msg}")
            
            self.access_token = data.get("plugin_token")
            expires_in = data.get("expire", 7200)  # Default 2 hours
            self.token_expiry = time.time() + expires_in - 300  # Refresh 5 min early
            
            print(f"DEBUG: Got Meegle token: {self.access_token[:20] if self.access_token else 'None'}..., expires in {expires_in}s")
            
            return self.access_token
            
        except requests.exceptions.RequestException as e:
            print(f"ERROR: Meegle token request failed: {e}")
            raise
    
    def _get_headers(self, idempotent_uuid=None):
        """Build request headers with token"""
        token = self.get_access_token()
        
        headers = {
            "Content-Type": "application/json",
            "X-PLUGIN-TOKEN": token,
            "X-USER-KEY": self.user_key  # REQUIRED - must be included
        }
        
        if idempotent_uuid:
            headers["X-IDEM-UUID"] = idempotent_uuid
        
        print(f"DEBUG: Request headers: X-PLUGIN-TOKEN={token[:20] if token else 'None'}..., X-USER-KEY={self.user_key}")
        
        return headers
    
    def get_work_items_filtered(self, work_item_type_keys=None, filters=None, page_size=50):
        """
        Get filtered work items using the /work_item/filter endpoint
        
        Args:
            work_item_type_keys: List of work item types (e.g., ["story"])
            filters: Additional filter criteria
            page_size: Number of items per page
        """
        url = f"{self.api_url}/{self.project_key}/work_item/filter"
        
        # Build payload based on Meegle API spec
        payload = {
            "page_size": page_size
        }
        
        if work_item_type_keys:
            payload["work_item_type_keys"] = work_item_type_keys
        
        # Add any additional filters
        if filters:
            payload.update(filters)
        
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
    
    def search_work_items(self, filters=None):
        """
        Search for work items (wrapper for get_work_items_filtered)
        
        Args:
            filters: Dict with filter criteria
                - assignee: User name or ID
                - status: Status name
                - start_date: ISO format date string
                - end_date: ISO format date string
                - language: Language value
        """
        # For now, we'll get all work items and filter client-side
        # This is a temporary solution until we figure out exact filter syntax
        
        # Get all work items first
        result = self.get_work_items_filtered(
            work_item_type_keys=None,  # Get all types
            page_size=100
        )
        
        return result
    
    def test_connection(self):
        """Test API connection by getting work items"""
        try:
            result = self.get_work_items_filtered(page_size=10)
            return result
        except Exception as e:
            raise
