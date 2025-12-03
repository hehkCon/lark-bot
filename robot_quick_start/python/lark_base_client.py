import requests
import json
from datetime import datetime
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
        Handles: datetime objects, strings with/without time, arrays
        Returns: YYYY-MM-DD format
        """
        if not date_field:
            return None
        
        # Handle array format (Lark sometimes returns arrays)
        if isinstance(date_field, list) and len(date_field) > 0:
            date_field = date_field[0]
            if isinstance(date_field, dict):
                date_field = date_field.get("text", "")
        
        # Convert to string
        date_str = str(date_field)
        
        # Extract just YYYY-MM-DD (first 10 chars)
        if len(date_str) >= 10:
            return date_str[:10]
        
        return date_str


    def _search_records(self, table_id: str, start_date: str = None, end_date: str = None, page_size: int = 500) -> List[Dict]:
        """
        ✅ FIXED: Search records with pagination support + infinite loop protection
        Fetches ALL records (handles 500 row limit with page_token)
        """
        url = f"{self.host}/open-apis/bitable/v1/apps/{self.app_token}/tables/{table_id}/records/search"

        print(f"DEBUG: Searching records from table {table_id} (with pagination)")
        print(f"DEBUG: Search URL: {url}")

        all_records = []
        page_token = None
        page_count = 0
        max_pages = 100  # ✅ SAFETY: Prevent infinite loops (max 100 pages = 50k rows)
        previous_page_token = None  # ✅ SAFETY: Detect if page_token repeats

        try:
            while page_count < max_pages:
                page_count += 1
                payload = {"page_size": page_size}
                
                if page_token:
                    payload["page_token"] = page_token
                    print(f"DEBUG: Fetching page {page_count} with token: {page_token[:20]}...")
                else:
                    print(f"DEBUG: Fetching page {page_count} (first page)")

                # ✅ SAFETY: Detect infinite loop (same token twice = API bug)
                if page_token == previous_page_token:
                    print(f"ERROR: Infinite loop detected! page_token repeated: {page_token}")
                    print(f"ERROR: Breaking to prevent infinite loop. Records so far: {len(all_records)}")
                    break
                
                previous_page_token = page_token

                response = requests.post(url, headers=self._get_headers(), json=payload, timeout=10)
                print(f"DEBUG: Page {page_count} response status: {response.status_code}")
                response.raise_for_status()

                data = response.json()

                if data.get("code") != 0:
                    print(f"ERROR: Lark API error on page {page_count}: {data.get('msg', 'Unknown error')}")
                    print(f"ERROR: Returning {len(all_records)} records fetched so far")
                    return all_records  # Return what we got so far

                page_records = data.get("data", {}).get("items", [])
                print(f"DEBUG: Page {page_count}: Fetched {len(page_records)} records")

                # ✅ SAFETY: If page is empty, stop (shouldn't happen but extra safety)
                if len(page_records) == 0:
                    print(f"DEBUG: Page {page_count} is empty, stopping pagination")
                    break

                all_records.extend(page_records)

                # Check if there are more pages
                page_token = data.get("data", {}).get("page_token")
                if not page_token:
                    print(f"DEBUG: No more pages. Total records fetched: {len(all_records)} across {page_count} pages")
                    break
                
                # ✅ SAFETY: Warn if approaching max pages
                if page_count >= max_pages - 5:
                    print(f"WARNING: Approaching max pages limit ({max_pages}). Already fetched {len(all_records)} records")

            # ✅ SAFETY: Final check if hit max pages without natural exit
            if page_count >= max_pages:
                print(f"ERROR: Hit maximum pages limit ({max_pages}). This might indicate an API issue.")
                print(f"ERROR: Returning {len(all_records)} records fetched so far")

            # Client-side date filtering if date range provided
            if start_date and end_date:
                print(f"DEBUG: Filtering dates from {start_date} to {end_date}")
                
                filtered_records = []
                for record in all_records:
                    fields = record.get("fields", {})

                    # Get date field - now using robust extraction
                    date_field = fields.get("date")
                    if not date_field:
                        continue

                    record_date_str = self._extract_date_string(date_field)
                    
                    if not record_date_str:
                        continue

                    # ✅ FIXED: String comparison with consistent format
                    if start_date <= record_date_str <= end_date:
                        filtered_records.append(record)

                print(f"DEBUG: Filtered to {len(filtered_records)} records between {start_date} and {end_date}")
                return filtered_records
            else:
                print(f"DEBUG: Returning all {len(all_records)} records (no date filter)")
                return all_records

        except requests.Timeout:
            print(f"ERROR: Request timeout while fetching records from {table_id}")
            print(f"ERROR: Returning {len(all_records)} records fetched so far")
            return all_records
        except Exception as e:
            print(f"ERROR: Failed to search records: {e}")
            print(f"ERROR: Returning {len(all_records)} records fetched so far")
            return all_records


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
