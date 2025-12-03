import requests
import json
from datetime import datetime
from typing import List, Dict, Any

class LarkBaseClient:
    def __init__(self, app_token: str, table_id: str, performance_table_id: str, token: str):
        self.app_token = app_token
        self.table_id = table_id
        self.performance_table_id = performance_table_id
        self.token = token
        self.host = "https://open.larksuite.com"
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8"
        }

    def _search_records(self, table_id: str, start_date: str = None, end_date: str = None, page_size: int = 500) -> List[Dict]:
        """Search records with optional DATE FILTERING - returns only records in date range."""
        url = f"{self.host}/open-apis/bitable/v1/apps/{self.app_token}/tables/{table_id}/records/search"
        
        # If date range provided, filter on server side
        if start_date and end_date:
            start_iso = f"{start_date}T00:00:00+00:00"
            end_iso = f"{end_date}T23:59:59+00:00"
            
            payload = {
                "filter": {
                    "conjunction": "and",
                    "conditions": [
                        {
                            "field_name": "date",
                            "operator": "isBetween",
                            "value": [start_iso, end_iso]
                        }
                    ]
                },
                "page_size": 500
            }
            print(f"DEBUG: Date filter: {start_date} to {end_date}")
        else:
            # No date filter - fetch all records from table
            payload = {"page_size": 500}
            print(f"DEBUG: No date filter - fetching all records")
        
        print(f"DEBUG: Searching records from table {table_id}")
        print(f"DEBUG: Search URL: {url}")
        print(f"DEBUG: Payload: {json.dumps(payload)}")
        
        try:
            response = requests.post(url, headers=self.headers, json=payload)
            print(f"DEBUG: Search response status: {response.status_code}")
            response.raise_for_status()
            
            data = response.json()
            print(f"DEBUG: Search response: {json.dumps(data, indent=2)[:500]}...")
            
            if data.get("code") != 0:
                print(f"ERROR: Lark API error: {data.get('msg', 'Unknown error')}")
                return []
            
            records = data.get("data", {}).get("items", [])
            if start_date and end_date:
                print(f"DEBUG: Fetched {len(records)} records (DATE FILTERED - no pagination needed)")
            else:
                print(f"DEBUG: Fetched {len(records)} records (no date filter)")
            return records
            
        except Exception as e:
            print(f"ERROR: Failed to search records: {e}")
            return []

    def get_user_records(self) -> List[Dict]:
        """Get all user records (no date filter needed)"""
        print("DEBUG: Fetching user data...")
        return self._search_records(self.table_id)

    def get_performance_records(self, start_date: str, end_date: str) -> List[Dict]:
        """Get performance records with SERVER-SIDE date filtering"""
        print(f"DEBUG: Fetching performance records for {start_date} to {end_date}")
        
        # Fetch records with date filter on server side
        records = self._search_records(self.performance_table_id, start_date, end_date)
        
        print(f"DEBUG: Received {len(records)} records from API (already date-filtered)")
        return records

    def get_user_data_dict(self) -> Dict[str, Dict]:
        """Get user data as dictionary keyed by email"""
        records = self.get_user_records()
        user_data = {}
        
        for record in records:
            fields = record.get("fields", {})
            
            # Extract email
            email_field = fields.get("email", [{}])[0]
            email = email_field.get("text", "").lower() if email_field else ""
            
            if not email:
                continue
            
            # Extract name
            name_field = fields.get("Text", [{}])[0]
            name = name_field.get("text", "") if name_field else ""
            
            # Extract department
            dept_field = fields.get("department", [{}])[0]
            department = dept_field.get("text", "") if dept_field else ""
            
            user_data[email] = {
                "name": name,
                "department": department,
                "record_id": record.get("record_id")
            }
            
            print(f"DEBUG: Added user: {name} ({email}) -> {department}")
        
        print(f"DEBUG: Fetched user data for {len(user_data)} users")
        print(f"DEBUG: User keys: {list(user_data.keys())}")
        
        return user_data


class PerformanceTracker:
    def __init__(self, lark_client: LarkBaseClient):
        self.client = lark_client

    def get_performance_records(self, date_range: tuple) -> List[Dict]:
        """Get performance records for date range"""
        start_date, end_date = date_range
        return self.client.get_performance_records(start_date, end_date)


class PerformanceCommands:
    def __init__(self, performance_tracker, user_data):
        self.performance_tracker = performance_tracker
        self.user_data = user_data
        self.team_mapping = {
            "amanda": "Amanda's Team",
            "dioulde": "Dioulde's Team", 
            "kath": "Kath's Team",
            "jello": "Jello's Team",
            "jonas": "Amanda's Team",
            "brent": "Amanda's Team",
            "angelika": "Kath's Team",
            "rachel": "Dioulde's Team",
            "job": "Jello's Team"
        }
        
        # Manager email mapping for accurate team filtering
        self.manager_emails = {
            "amanda's team": ["amanda.g@intentt.com", "jonas.f@intentt.com", "brent.l@intentt.com"],
            "dioulde's team": ["dioulde.n@intentt.com", "rachel.l@intentt.com"],
            "kath's team": ["kath.g@intentt.com", "angelika.m@intentt.com"],
            "jello's team": ["jello.c@intentt.com", "job.c@intentt.com"]
        }

    def _parse_date_range(self, text: str) -> tuple:
        """Parse date range from command text"""
        from datetime import timedelta
        
        text_lower = text.lower()
        today = datetime.now().date()
        
        if "yesterday" in text_lower:
            start = today - timedelta(days=1)
            end = start
        elif "last 7" in text_lower or "last7" in text_lower:
            start = today - timedelta(days=6)
            end = today
        elif "mtd" in text_lower:
            start = today.replace(day=1)
            end = today
        else:
            start = end = today
        
        return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")

    def _get_team_records(self, team_name: str, date_range: tuple) -> List[Dict]:
        """Get performance records for specific team by campaign_manager emails"""
        all_records = self.performance_tracker.get_performance_records(date_range)
        team_records = []
        
        # Get target manager emails for this team
        target_emails = self.manager_emails.get(team_name.lower(), [])
        
        for record in all_records:
            fields = record.get("fields", {})
            # Handle campaign_manager field safely (it's a URL field)
            campaign_manager_field = fields.get("campaign_manager", [{}])[0]
            campaign_manager = campaign_manager_field.get("text", "").lower() if campaign_manager_field else ""
            
            # Match any of the team managers
            if any(email in campaign_manager for email in target_emails):
                team_records.append(record)
        
        print(f"DEBUG: Found {len(team_records)} records for {team_name} (managers: {target_emails})")
        return team_records

    def _get_user_records(self, email: str, date_range: tuple) -> List[Dict]:
        """Get performance records for specific user by campaign_manager email"""
        all_records = self.performance_tracker.get_performance_records(date_range)
        user_records = []
        
        for record in all_records:
            fields = record.get("fields", {})
            campaign_manager_field = fields.get("campaign_manager", [{}])[0]
            campaign_manager = campaign_manager_field.get("text", "").lower() if campaign_manager_field else ""
            
            if email in campaign_manager:
                user_records.append(record)
        
        print(f"DEBUG: Found {len(user_records)} records for user {email}")
        return user_records

    def _aggregate_performance(self, records: List[Dict]) -> Dict[str, Any]:
        """Aggregate performance metrics from records - calculates ROI with logging"""
        total_spend = 0
        total_revenue = 0
        total_profit = 0
        
        for i, record in enumerate(records, 1):
            fields = record.get("fields", {})
            
            # Handle number fields safely (some may be lists, some direct numbers)
            spend = float(fields.get("spend", 0) or 0)
            revenue = float(fields.get("revenue", 0) or 0)
            profit = float(fields.get("profit", 0) or 0)
            
            total_spend += spend
            total_revenue += revenue
            total_profit += profit
            
            print(f"DEBUG: Record {i}: spend=${spend:.2f} revenue=${revenue:.2f} profit=${profit:.2f}")
        
        # ROI = (Profit / Spend) * 100%
        roi = (total_profit / total_spend * 100) if total_spend > 0 else 0
        
        print(f"DEBUG: TOTALS - Records: {len(records)}, Spend: ${total_spend:.2f}, Revenue: ${total_revenue:.2f}, Profit: ${total_profit:.2f}, ROI: {roi:.1f}%")
        
        return {
            "records": len(records),
            "spend": total_spend,
            "revenue": total_revenue,
            "profit": total_profit,
            "roi": roi
        }

    def _format_performance_message(self, title: str, date_range: tuple, records: List[Dict]) -> str:
        """Format performance message with quoted block style"""
        start_date, end_date = date_range

        if not records:
            date_label = f"{start_date}" if start_date == end_date else f"{start_date} to {end_date}"
            return f"📊 **{title} - {date_label}**\n\nNo performance data found for this period."

        agg = self._aggregate_performance(records)
        date_label = f"{start_date}" if start_date == end_date else f"{start_date} to {end_date}"

        message = f"📊 **{title} - {date_label}**\n"
        message += f"> Records: {agg['records']}\n"
        message += f"> Spend: ${agg['spend']:,.0f}\n"
        message += f"> Revenue: ${agg['revenue']:,.0f}\n"
        message += f"> Profit: ${agg['profit']:,.0f}\n"
        message += f"> ROI: {agg['roi']:.1f}%\n"

        return message

    def handle_performance_command(self, text: str, user_open_id: str) -> str:
        """Main command handler"""
        import re
        
        text_parts = text.lower().strip().split()
        if len(text_parts) < 2:
            return self._get_help_text()
        
        command_type = text_parts[1]
        date_range = self._parse_date_range(text)
        
        # Team queries (perf team, perf amanda, etc.)
        if command_type in self.team_mapping:
            team_name = self.team_mapping[command_type]
            records = self._get_team_records(team_name, date_range)
            return self._format_performance_message(team_name, date_range, records)
        
        # All teams summary
        elif command_type == "team":
            records = self.performance_tracker.get_performance_records(date_range)
            return self._format_performance_message("All Teams", date_range, records)
        
        # Personal performance ("perf me")
        elif command_type == "me":
            records = self.performance_tracker.get_performance_records(date_range)
            return self._format_performance_message("Your Performance", date_range, records)
        
        # Email-based user lookup
        elif "@" in command_type:
            # Extract clean email (remove mailto: and brackets)
            clean_email = re.sub(r'\[|\]|\(mailto:|\)', '', command_type).strip().lower()
            records = self._get_user_records(clean_email, date_range)
            
            # Get user name from user_data if available
            user_name = self.user_data.get(clean_email, {}).get("name", clean_email.split('@')[0].title())
            return self._format_performance_message(f"{user_name}'s Performance", date_range, records)
        
        return self._get_help_text()

    def _get_help_text(self) -> str:
        """Help text for performance commands"""
        return """📊 **Performance Commands**

**Your Performance:** `perf me [period]`
**All Teams:** `perf team [period]`
**Specific Teams:** `perf amanda/kath/dioulde/jello [period]`

**Periods:** (default=today) yesterday | last 7 | mtd

**Examples:**
• `perf amanda yesterday`
• `perf team last 7`
• `perf kath mtd`
• `perf jonas.f@intentt.com last 7`"""

