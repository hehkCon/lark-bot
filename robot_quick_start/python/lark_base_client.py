import requests
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any


class LarkBaseClient:
    def __init__(self, app_token: str, table_id: str, performance_table_id: str, token_manager):
        self.app_token = app_token
        self.table_id = table_id
        self.performance_table_id = performance_table_id
        self.token_manager = token_manager
        self.host = "https://open.larksuite.com"
        self.headers = {
            "Content-Type": "application/json; charset=utf-8"
        }


    def _get_headers(self):
        token = self.token_manager.get_token()
        headers = self.headers.copy()
        headers["Authorization"] = f"Bearer {token}"
        return headers


    def _extract_date_string(self, date_field) -> str:
        """
        ✅ FIXED: Extract date string from various formats
        Handles: Unix timestamps (milliseconds), datetime objects, strings with/without time, arrays
        Returns: YYYY-MM-DD format
        """
        if not date_field:
            return None
        
        # Handle array format (Lark sometimes returns arrays)
        if isinstance(date_field, list) and len(date_field) > 0:
            date_field = date_field[0]
            if isinstance(date_field, dict):
                date_field = date_field.get("text", "")
        
        # ✅ CRITICAL FIX: Handle Unix timestamp in milliseconds
        if isinstance(date_field, (int, float)):
            # Convert milliseconds to seconds
            timestamp_seconds = date_field / 1000
            dt = datetime.fromtimestamp(timestamp_seconds)
            return dt.strftime("%Y-%m-%d")
        
        # Convert to string
        date_str = str(date_field)
        
        # Extract just YYYY-MM-DD (first 10 chars)
        if len(date_str) >= 10:
            return date_str[:10]
        
        return date_str


    def _extract_email_from_field(self, email_field) -> str:
        """
        ✅ FIXED: Extract email from various field formats
        Handles: arrays with text objects, strings, None values
        Returns: Email string or empty string
        """
        if not email_field:
            return ""
        
        # Handle array format: [{"text": "email@domain.com", "type": "text"}]
        if isinstance(email_field, list) and len(email_field) > 0:
            item = email_field[0]
            if isinstance(item, dict):
                email = item.get("text", "").strip()
                # Skip "-" or "missing" indicators
                if email and email != "-":
                    return email.lower()
                return ""
            elif isinstance(item, str):
                email = item.strip().lower()
                if email and email != "-":
                    return email
                return ""
        
        # Handle string format
        if isinstance(email_field, str):
            email = email_field.strip().lower()
            if email and email != "-":
                return email
            return ""
        
        return ""


    def _search_records(self, table_id: str, start_date: str = None, end_date: str = None, page_size: int = 500) -> List[Dict]:
        """
        ✅ OPTIMIZED: Efficient pagination - stops early, minimal API calls
        
        IMPROVEMENTS:
        - Stop when page records < page_size (natural end of pagination)
        - No arbitrary 100-page limit
        - Simpler logic with while True loop
        """
        url = f"{self.host}/open-apis/bitable/v1/apps/{self.app_token}/tables/{table_id}/records/search"

        all_records = []
        page_token = None

        try:
            while True:  # Keep going until we're told to stop
                payload = {"page_size": page_size}
                
                if page_token:
                    payload["page_token"] = page_token
                
                response = requests.post(url, headers=self._get_headers(), json=payload, timeout=10)
                response.raise_for_status()

                data = response.json()

                if data.get("code") != 0:
                    print(f"ERROR: Lark API error: {data.get('msg', 'Unknown error')}")
                    return all_records

                page_records = data.get("data", {}).get("items", [])
                all_records.extend(page_records)

                # ✅ EFFICIENT: Stop when we get fewer records than requested
                # This means we're at the last page
                if len(page_records) < page_size:
                    print(f"DEBUG: Pagination complete. Total records: {len(all_records)}")
                    break

                # ✅ Also check for page_token (API's official end signal)
                page_token = data.get("data", {}).get("page_token")
                if not page_token:
                    print(f"DEBUG: Pagination complete. Total records: {len(all_records)}")
                    break

            # Client-side date filtering if date range provided
            if start_date and end_date:
                print(f"DEBUG: Filtering {len(all_records)} records for date range {start_date} to {end_date}")
                filtered_records = []
                for record in all_records:
                    fields = record.get("fields", {})
                    date_field = fields.get("date")
                    if not date_field:
                        continue

                    record_date_str = self._extract_date_string(date_field)
                    if not record_date_str:
                        continue

                    if start_date <= record_date_str <= end_date:
                        filtered_records.append(record)

                print(f"DEBUG: Filtered to {len(filtered_records)} records in date range {start_date} to {end_date}")
                return filtered_records
            else:
                return all_records

        except requests.Timeout:
            print(f"ERROR: Request timeout")
            return all_records
        except Exception as e:
            print(f"ERROR: Failed to search records: {e}")
            return all_records


    def get_user_records(self) -> List[Dict]:
        """Get all user records (no date filter needed)"""
        print("DEBUG: Fetching user data...")
        return self._search_records(self.table_id)


    def get_performance_records(self, start_date: str, end_date: str) -> List[Dict]:
        """Get performance records with CLIENT-SIDE date filtering"""
        print(f"DEBUG: Fetching performance records for {start_date} to {end_date}")

        records = self._search_records(self.performance_table_id, start_date, end_date)

        print(f"DEBUG: Received {len(records)} records from API")
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
            campaign_manager_field = fields.get("campaign_manager", "")
            
            # ✅ FIXED: Use _extract_email_from_field to properly parse campaign_manager
            manager_email = self.client._extract_email_from_field(campaign_manager_field)
            
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
            "revenue_target": 20000.0 / num_media_buyers,
            "profit_target": 5000.0 / num_media_buyers
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
