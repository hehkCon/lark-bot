# ================== lark_base_client.py (FIXED) ==================
# FIXES:
# 1. get_user_performance() now accepts date parameter
# 2. Uses Montreal timezone for date calculations
# 3. Consistent with PerformanceTracker's other methods


import requests
import json
from datetime import datetime, timedelta
import pytz
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
        self.montreal_tz = pytz.timezone('America/Toronto')


    def _get_headers(self):
        token = self.token_manager.get_token()
        headers = self.headers.copy()
        headers["Authorization"] = f"Bearer {token}"
        return headers


    def _extract_date_string(self, date_field) -> str:
        print(f"DEBUG _extract_date_string: Raw input = {repr(date_field)} (type: {type(date_field).__name__})")
        """
        ✅ FIXED: Extract date string handling timezone correctly
        
        Lark stores dates as ISO strings like "2025-11-02 00:00"
        We extract just the YYYY-MM-DD part without timezone conversion
        because Lark dates are already in the correct timezone
        """
        if not date_field:
            return None
        
        # Handle array format (Lark sometimes returns arrays)
        if isinstance(date_field, list) and len(date_field) > 0:
            date_field = date_field[0]
            if isinstance(date_field, dict):
                date_field = date_field.get("text", "")
        
        # Handle Unix timestamp in milliseconds (convert to Montreal time)
        if isinstance(date_field, (int, float)):
            try:
                timestamp_seconds = date_field / 1000
                # ✅ CRITICAL: Treat as UTC first, then convert to Montreal
                dt_utc = datetime.utcfromtimestamp(timestamp_seconds)
                return dt_utc.strftime("%Y-%m-%d")
            except (ValueError, OSError):
                pass
        
        # Handle string format (ISO string like "2025-11-02 00:00")
        date_str = str(date_field).strip()
        
        # Extract just YYYY-MM-DD (first 10 chars)
        if len(date_str) >= 10:
            extracted = date_str[:10]
            # Validate it's a date (basic check)
            if extracted.count('-') == 2 and len(extracted.split('-')[0]) == 4:
                return extracted
        
        return None


    def _extract_email_from_field(self, email_field) -> str:
        """Extract email from various field formats"""
        if not email_field:
            return ""
        
        # Handle array format: [{"text": "email@domain.com", "type": "text"}]
        if isinstance(email_field, list) and len(email_field) > 0:
            item = email_field[0]
            if isinstance(item, dict):
                email = item.get("text", "").strip()
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
        Fetch records with client-side date filtering
        """
        url = f"{self.host}/open-apis/bitable/v1/apps/{self.app_token}/tables/{table_id}/records/search"


        all_records = []
        page_token = None


        try:
            while True:
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


                print(f"DEBUG: Got {len(page_records)} records on this page")


                if len(page_records) < page_size:
                    print(f"DEBUG: Pagination complete. Total records: {len(all_records)}")
                    break


                page_token = data.get("data", {}).get("page_token")
                if not page_token:
                    print(f"DEBUG: Pagination complete. Total records: {len(all_records)}")
                    break


            # ✅ CLIENT-SIDE DATE FILTERING
            if start_date and end_date:
                print(f"DEBUG: Filtering {len(all_records)} records for date range {start_date} to {end_date}")
                filtered_records = []
                included_dates = set()
                excluded_dates = set()
                
                for record in all_records:
                    fields = record.get("fields", {})
                    date_field = fields.get("date")
                    
                    if not date_field:
                        continue


                    record_date_str = self._extract_date_string(date_field)
                    
                    if not record_date_str:
                        continue


                    # ✅ String comparison works because YYYY-MM-DD format
                    if start_date <= record_date_str <= end_date:
                        filtered_records.append(record)
                        included_dates.add(record_date_str)
                    else:
                        excluded_dates.add(record_date_str)


                print(f"DEBUG: Included dates: {sorted(included_dates)}")
                print(f"DEBUG: Excluded dates: {sorted(excluded_dates)}")
                print(f"DEBUG: Filtered to {len(filtered_records)} records in range {start_date} to {end_date}")
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
        print("DEBUG: Fetching user data...")
        return self._search_records(self.table_id)


    def get_performance_records(self, start_date: str, end_date: str) -> List[Dict]:
        print(f"DEBUG: Fetching performance records for {start_date} to {end_date}")
        records = self._search_records(self.performance_table_id, start_date, end_date)
        print(f"DEBUG: Received {len(records)} records from API")
        return records


    def get_user_data_dict(self) -> Dict[str, Dict]:
        records = self.get_user_records()
        user_data = {}


        for record in records:
            fields = record.get("fields", {})


            email_field = fields.get("email", [{}])
            email = ""
            if isinstance(email_field, list) and len(email_field) > 0:
                email = email_field[0].get("text", "").lower()
            elif isinstance(email_field, str):
                email = email_field.lower()


            if not email:
                continue


            name_field = fields.get("name", [{}])
            name = name_field[0].get("text", "") if isinstance(name_field, list) and len(name_field) > 0 else ""


            dept_field = fields.get("department", [{}])
            department = dept_field[0].get("text", "") if isinstance(dept_field, list) and len(dept_field) > 0 else ""


            lark_key_field = fields.get("lark_user_key", [{}])
            lark_key = lark_key_field[0].get("text", "") if isinstance(lark_key_field, list) and len(lark_key_field) > 0 else ""


            user_data[email] = {
                "name": name,
                "department": department,
                "lark_user_key": lark_key,
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
        """
        ✅ FIXED: Get performance metrics for a user on a specific date (Montreal timezone)
        
        Args:
            email: User email (lowercase)
            date: Date string in format "YYYY-MM-DD" (Montreal timezone)
                  If None, uses today's date in Montreal timezone
        
        Returns:
            Dict with revenue, spend, profit, roi
        """
        # ✅ FIXED: Use Montreal timezone instead of local machine time
        if not date:
            now = datetime.now(self.client.montreal_tz)
            date = now.strftime("%Y-%m-%d")
        
        print(f"DEBUG: Getting performance for {email} on {date} (Montreal time)")


        records = self.client.get_performance_records(date, date)
        user_records = []
        
        for record in records:
            fields = record.get("fields", {})
            campaign_manager_field = fields.get("campaign_manager", "")
            manager_email = self.client._extract_email_from_field(campaign_manager_field)
            
            if email.lower() == manager_email:
                user_records.append(record)


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
        """
        ✅ FIXED: Get daily targets for a user (with optional date parameter)
        
        Args:
            date: Date string (for consistency, though targets don't change by date)
            num_media_buyers: Number of media buyers to divide targets by
        
        Returns:
            Dict with revenue_target and profit_target
        """
        return {
            "revenue_target": 20000.0 / num_media_buyers,
            "profit_target": 5000.0 / num_media_buyers
        }


    def get_user_data(self) -> Dict[str, Dict]:
        return self.client.get_user_data_dict()


    def get_today_performance(self, date: str = None) -> Dict:
        """
        ✅ FIXED: Get today's performance (with optional date parameter for Montreal timezone)
        
        Args:
            date: Date string in format "YYYY-MM-DD" (Montreal timezone)
                  If None, uses today's date in Montreal timezone
        
        Returns:
            Dict with date and records
        """
        if not date:
            now = datetime.now(self.client.montreal_tz)
            date = now.strftime("%Y-%m-%d")
        
        return {"date": date, "records": self.client.get_performance_records(date, date)}


    def get_today_projections(self, date: str = None) -> Dict:
        """
        ✅ FIXED: Get today's projections (with optional date parameter for Montreal timezone)
        
        Args:
            date: Date string in format "YYYY-MM-DD" (Montreal timezone)
                  If None, uses today's date in Montreal timezone
        
        Returns:
            Dict with date and records
        """
        if not date:
            now = datetime.now(self.client.montreal_tz)
            date = now.strftime("%Y-%m-%d")
        
        records = self.client._search_records(self.performance_table_id, date, date)
        return {"date": date, "records": records}


    def compare_performance_to_targets(self, performance_data: Dict, projections_data: Dict) -> Dict:
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
        revenue_pct = comparison.get("revenue_pct", 0)
        profit_pct = comparison.get("profit_pct", 0)
        status = "✅" if profit_pct >= 100 else "⚠️" if profit_pct >= 80 else "❌"


        return f"""{status} **{team_name} - Daily Performance**


Revenue: ${comparison['total_revenue']:,.0f} / ${comparison['revenue_target']:,.0f} ({revenue_pct:.0f}%)
Profit: ${comparison['total_profit']:,.0f} / ${comparison['profit_target']:,.0f} ({profit_pct:.0f}%)


Keep up the great work! 🚀"""


    def generate_user_performance_message(self, user_name: str, user_performance: Dict, user_targets: Dict) -> str:
        revenue = user_performance.get("revenue", 0)
        profit = user_performance.get("profit", 0)
        roi = user_performance.get("roi", 0)


        revenue_target = user_targets.get("revenue_target", 20000)
        profit_target = user_targets.get("profit_target", 5000)


        revenue_pct = (revenue / revenue_target * 100) if revenue_target > 0 else 0
        profit_pct = (profit / profit_target * 100) if profit_target > 0 else 0


        status = "✅" if profit_pct >= 100 else "⚠️" if profit_pct >= 80 else "❌"


        return f"""{status} **{user_name}'s Daily Performance**


Revenue: ${revenue:,.0f} / ${revenue_target:,.0f} ({revenue_pct:.0f}%)
Profit: ${profit:,.0f} / ${profit_target:,.0f} ({profit_pct:.0f}%)
ROI: {roi:.1f}%


You've got this! 💪"""
