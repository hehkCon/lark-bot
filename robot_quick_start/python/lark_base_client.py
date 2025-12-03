import requests
import json
from datetime import datetime
from typing import List, Dict, Any


class LarkBaseClient:
    def __init__(self, app_token: str, table_id: str, performance_table_id: str, token_manager):
        self.app_token = app_token
        self.table_id = table_id
        self.performance_table_id = performance_table_id
        self.token_manager = token_manager  # Use token manager here
        self.host = "https://open.larksuite.com"
        self.headers = {
            "Content-Type": "application/json; charset=utf-8"
        }


    def _get_headers(self):
        token = self.token_manager.get_token()  # Always get fresh token
        headers = self.headers.copy()
        headers["Authorization"] = f"Bearer {token}"
        return headers


    def _normalize_date(self, date_str: str) -> str:
        """
        Convert date string to YYYY/MM/DD format (matching Lark Base format)
        Input: 2025-11-14 or 2025/11/14
        Output: 2025/11/14
        """
        if not date_str:
            return None
        
        # Replace dashes with slashes for consistency
        return date_str.replace("-", "/")


    def _search_records(self, table_id: str, start_date: str = None, end_date: str = None, page_size: int = 500) -> List[Dict]:
        """Search records - fetch all and filter client-side"""
        url = f"{self.host}/open-apis/bitable/v1/apps/{self.app_token}/tables/{table_id}/records/search"

        payload = {"page_size": page_size}
        print(f"DEBUG: Searching records from table {table_id} (client-side filtering)")
        print(f"DEBUG: Search URL: {url}")

        try:
            response = requests.post(url, headers=self._get_headers(), json=payload, timeout=10)
            print(f"DEBUG: Search response status: {response.status_code}")
            response.raise_for_status()

            data = response.json()

            if data.get("code") != 0:
                print(f"ERROR: Lark API error: {data.get('msg', 'Unknown error')}")
                return []

            all_records = data.get("data", {}).get("items", [])
            print(f"DEBUG: Fetched {len(all_records)} total records from API")

            # Client-side date filtering if date range provided
            if start_date and end_date:
                # Normalize dates to YYYY/MM/DD format (matching Lark Base)
                start_normalized = self._normalize_date(start_date)
                end_normalized = self._normalize_date(end_date)
                
                print(f"DEBUG: Filtering dates from {start_normalized} to {end_normalized}")
                
                filtered_records = []
                for record in all_records:
                    fields = record.get("fields", {})

                    # Get date field (first column)
                    date_field = fields.get("date")
                    if not date_field:
                        continue

                    # Extract date string
                    if isinstance(date_field, list) and len(date_field) > 0:
                        record_date = date_field[0].get("text", "") if isinstance(date_field[0], dict) else str(date_field[0])
                    else:
                        record_date = str(date_field)

                    # Normalize to YYYY/MM/DD
                    record_date_normalized = record_date.replace("-", "/") if record_date else ""
                    record_date_str = record_date_normalized[:10] if len(record_date_normalized) >= 10 else record_date_normalized

                    # Compare dates
                    if start_normalized <= record_date_str <= end_normalized:
                        filtered_records.append(record)

                print(f"DEBUG: Filtered to {len(filtered_records)} records between {start_normalized} and {end_normalized}")
                return filtered_records
            else:
                print(f"DEBUG: Returning all {len(all_records)} records (no date filter)")
                return all_records

        except requests.Timeout:
            print(f"ERROR: Request timeout while fetching records from {table_id}")
            return []
        except Exception as e:
            print(f"ERROR: Failed to search records: {e}")
            return []


    def get_user_records(self) -> List[Dict]:
        """Get all user records (no date filter needed)"""
        print("DEBUG: Fetching user data...")
        return self._search_records(self.table_id)


    def get_performance_records(self, start_date: str, end_date: str) -> List[Dict]:
        """Get performance records with CLIENT-SIDE date filtering"""
        print(f"DEBUG: Fetching performance records for {start_date} to {end_date}")

        records = self._search_records(self.performance_table_id, start_date, end_date)

        print(f"DEBUG: Received {len(records)} records from API (already date-filtered client-side)")
        return records


    def get_user_data_dict(self) -> Dict[str, Dict]:
        """Get user data as dictionary keyed by email"""
        records = self.get_user_records()
        user_data = {}

        for record in records:
            fields = record.get("fields", {})

            # Extract email
            email_field = fields.get("email", [{}])
            email = ""
            if isinstance(email_field, list) and len(email_field) > 0:
                email = email_field[0].get("text", "").lower()
            elif isinstance(email_field, str):
                email = email_field.lower()

            if not email:
                continue

            # Extract name
            name_field = fields.get("name", [{}])
            name = name_field[0].get("text", "") if isinstance(name_field, list) and len(name_field) > 0 else ""

            # Extract department
            dept_field = fields.get("department", [{}])
            department = dept_field[0].get("text", "") if isinstance(dept_field, list) and len(dept_field) > 0 else ""

            # Extract lark_user_key
            lark_user_key_field = fields.get("lark_user_key", [{}])
            lark_user_key = lark_user_key_field[0].get("text", "") if isinstance(lark_user_key_field, list) and len(lark_user_key_field) > 0 else ""

            user_data[email] = {
                "name": name,
                "department": department,
                "lark_user_key": lark_user_key,
                "record_id": record.get("record_id")
            }

            print(f"DEBUG: Added user: {name} ({email}) -> {department}")

        print(f"DEBUG: Fetched user data for {len(user_data)} users")
        return user_data



class PerformanceTracker:
    def __init__(self, lark_client: LarkBaseClient):
        self.client = lark_client
        self.performance_table_id = lark_client.performance_table_id


    def get_user_performance(self, email: str, date: str = None) -> Dict[str, float]:
        """Get performance metrics for a specific user on a specific date"""
        from datetime import datetime as dt

        if not date:
            date = dt.now().strftime("%Y-%m-%d")

        records = self.client.get_performance_records(date, date)
        user_records = []
        
        for record in records:
            fields = record.get("fields", {})
            campaign_manager_field = fields.get("campaign_manager", [{}])
            manager_email = ""
            
            if isinstance(campaign_manager_field, list) and len(campaign_manager_field) > 0:
                manager_email = campaign_manager_field[0].get("text", "").lower()
            elif isinstance(campaign_manager_field, str):
                manager_email = campaign_manager_field.lower()

            if email.lower() == manager_email:
                user_records.append(record)

        # Sum across all records (all platforms for this user on this date)
        total_revenue = 0
        total_spend = 0
        total_profit = 0
        
        for r in user_records:
            try:
                revenue = float(r.get("fields", {}).get("revenue", 0) or 0)
                spend = float(r.get("fields", {}).get("spend", 0) or 0)
                profit = float(r.get("fields", {}).get("profit", 0) or 0)
                
                total_revenue += revenue
                total_spend += spend
                total_profit += profit
            except (ValueError, TypeError):
                continue

        roi = (total_profit / total_spend * 100) if total_spend > 0 else 0

        return {
            "revenue": total_revenue,
            "spend": total_spend,
            "profit": total_profit,
            "roi": roi
        }


    def get_daily_user_target(self, date: str = None, num_media_buyers: int = 9) -> Dict[str, float]:
        """Get daily performance targets for users - FIXED targets"""
        from datetime import datetime as dt

        if not date:
            date = dt.now().strftime("%Y-%m-%d")

        # Default targets (adjust as needed)
        return {
            "revenue_target": 20000.0 / num_media_buyers,  # ~$2,222 per person
            "profit_target": 5000.0 / num_media_buyers      # ~$556 per person
        }


    def get_user_data(self) -> Dict[str, Dict]:
        """Get all user data from user info table"""
        return self.client.get_user_data_dict()


    def get_today_performance(self) -> Dict:
        """Fetch today's performance data"""
        from datetime import datetime as dt

        today = dt.now().strftime("%Y-%m-%d")
        return {"date": today, "records": self.client.get_performance_records(today, today)}


    def get_today_projections(self) -> Dict:
        """Fetch today's projection/target data"""
        from datetime import datetime as dt

        today = dt.now().strftime("%Y-%m-%d")
        records = self.client._search_records(self.performance_table_id, today, today)
        return {"date": today, "records": records}


    def compare_performance_to_targets(self, performance_data: Dict, projections_data: Dict) -> Dict:
        """Compare performance vs targets"""
        performance_records = performance_data.get("records", [])
        
        total_revenue = 0
        total_profit = 0
        
        for r in performance_records:
            try:
                revenue = float(r.get("fields", {}).get("revenue", 0) or 0)
                profit = float(r.get("fields", {}).get("profit", 0) or 0)
                total_revenue += revenue
                total_profit += profit
            except (ValueError, TypeError):
                continue

        # Fixed targets
        revenue_target = 180000
        profit_target = 45000

        return {
            "total_revenue": total_revenue,
            "total_profit": total_profit,
            "revenue_target": revenue_target,
            "profit_target": profit_target,
            "revenue_pct": (total_revenue / revenue_target * 100) if revenue_target > 0 else 0,
            "profit_pct": (total_profit / profit_target * 100) if profit_target > 0 else 0
        }


    def generate_performance_message(self, team_name: str, comparison: Dict) -> str:
        """Generate formatted team performance message"""
        revenue_pct = comparison.get("revenue_pct", 0)
        profit_pct = comparison.get("profit_pct", 0)

        status = "✅" if profit_pct >= 100 else "⚠️" if profit_pct >= 80 else "❌"

        message = f"""{status} **{team_name} - Daily Performance**

Revenue: ${comparison['total_revenue']:,.0f} / ${comparison['revenue_target']:,.0f} ({revenue_pct:.0f}%)
Profit: ${comparison['total_profit']:,.0f} / ${comparison['profit_target']:,.0f} ({profit_pct:.0f}%)

Keep up the great work! 🚀"""

        return message


    def generate_user_performance_message(self, user_name: str, user_performance: Dict, user_targets: Dict) -> str:
        """Generate personalized message for individual user"""
        revenue = user_performance.get("revenue", 0)
        profit = user_performance.get("profit", 0)
        roi = user_performance.get("roi", 0)

        revenue_target = user_targets.get("revenue_target", 20000)
        profit_target = user_targets.get("profit_target", 5000)

        revenue_pct = (revenue / revenue_target * 100) if revenue_target > 0 else 0
        profit_pct = (profit / profit_target * 100) if profit_target > 0 else 0

        status = "✅" if profit_pct >= 100 else "⚠️" if profit_pct >= 80 else "❌"

        message = f"""{status} **{user_name}'s Daily Performance**

Revenue: ${revenue:,.0f} / ${revenue_target:,.0f} ({revenue_pct:.0f}%)
Profit: ${profit:,.0f} / ${profit_target:,.0f} ({profit_pct:.0f}%)
ROI: {roi:.1f}%

You've got this! 💪"""

        return message
