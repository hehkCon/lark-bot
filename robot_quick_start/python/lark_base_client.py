import requests
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

class PerformanceTracker:
    def __init__(
        self,
        app_token: str,
        performance_table_id: str,
        projections_table_id: str,
        user_info_table_id: str,
        tenant_access_token: str,
        host: str = "https://open.larksuite.com"
    ):
        self.app_token = app_token
        self.performance_table_id = performance_table_id
        self.projections_table_id = projections_table_id
        self.user_info_table_id = user_info_table_id
        self.tenant_access_token = tenant_access_token
        self.host = host
        self.headers = {
            "Authorization": f"Bearer {tenant_access_token}",
            "Content-Type": "application/json; charset=utf-8"
        }

    def _search_records(self, table_id: str, page_size: int = 100) -> List[Dict]:
        """Search records using the new Search Records API (POST)"""
        url = f"{self.host}/open-apis/bitable/v1/apps/{self.app_token}/tables/{table_id}/records/search"
        
        payload = {
            "page_size": page_size
        }
        
        print(f"DEBUG: Searching records from table {table_id}")
        print(f"DEBUG: Search URL: {url}")
        print(f"DEBUG: Headers: {dict(self.headers)}")
        print(f"DEBUG: Payload: {json.dumps(payload)}")
        
        try:
            response = requests.post(url, headers=self.headers, json=payload)
            response.raise_for_status()
            
            data = response.json()
            print(f"DEBUG: Search response status: {response.status_code}")
            print(f"DEBUG: Search response: {json.dumps(data, indent=2)[:1000]}")
            
            if data.get("code") != 0:
                print(f"ERROR: Lark API error: {data.get('msg', 'Unknown error')}")
                return []
            
            records = data.get("data", {}).get("items", [])
            print(f"DEBUG: Fetched {len(records)} records")
            return records
            
        except requests.exceptions.HTTPError as e:
            print(f"ERROR: HTTP error {response.status_code}: {response.text}")
            return []
        except Exception as e:
            print(f"ERROR: Failed to search records: {e}")
            return []

    def get_user_data(self) -> Dict[str, Dict]:
        """Fetch user info from user_info_table"""
        print("DEBUG: Fetching user data...")
        records = self._search_records(self.user_info_table_id, page_size=500)
        
        user_data = {}
        for record in records:
            fields = record.get("fields", {})
            
            # Match your actual table field names
            name = fields.get("Text", [{}])[0].get("text", "").strip() or "Unknown"
            email_field = fields.get("email", [{}])[0]
            email = email_field.get("text", "").strip() if email_field else ""
            team = fields.get("department", [{}])[0].get("text", "").strip()
            
            if name and email:
                user_data[email.lower()] = {
                    "name": name,
                    "email": email,
                    "team": team
                }
                print(f"DEBUG: Added user: {name} ({email}) -> {team}")
        
        print(f"DEBUG: Fetched user data for {len(user_data)} users")
        print(f"DEBUG: User keys: {list(user_data.keys())}")
        return user_data

    def get_performance_records(self, date_range: tuple) -> List[Dict]:
        """Get performance records for date range using Search API"""
        start_date, end_date = date_range
        print(f"DEBUG: Fetching performance records for {start_date} to {end_date}")
        
        # Convert dates to milliseconds for comparison
        start_ms = int(datetime.strptime(start_date, "%Y-%m-%d").timestamp() * 1000)
        end_ms = int(datetime.strptime(end_date, "%Y-%m-%d").timestamp() * 1000) + 86399999  # End of day
        
        records = self._search_records(self.performance_table_id, page_size=500)
        filtered_records = []
        
        for record in records:
            fields = record.get("fields", {})
            record_date_ms = fields.get("date", [0])[0]
            
            if start_ms <= record_date_ms <= end_ms:
                filtered_records.append(record)
        
        print(f"DEBUG: Filtered to {len(filtered_records)} performance records in date range")
        return filtered_records

    def get_projections(self) -> List[Dict]:
        """Get projection/target records using Search API"""
        print("DEBUG: Fetching projections...")
        return self._search_records(self.projections_table_id, page_size=100)

