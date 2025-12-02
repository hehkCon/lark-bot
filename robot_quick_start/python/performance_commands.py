import re
from datetime import datetime, timedelta
from typing import Dict, List, Any

class PerformanceCommands:
    def __init__(self, tracker, user_data: Dict[str, Dict]):
        self.tracker = tracker
        self.user_data = user_data
        self.team_mapping = {
            "amanda": "Amanda's Team",
            "kath": "Kath's Team", 
            "dioulde": "Dioulde's Team",
            "jello": "Jello's Team",
            "jonas": "Amanda's Team",
            "brent": "Amanda's Team",
            "angelika": "Kath's Team",
            "rachel": "Dioulde's Team",
            "job": "Jello's Team"
        }

    def _parse_date_range(self, text: str) -> tuple:
        """Parse date range from command text"""
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
        """Get performance records for specific team"""
        all_records = self.tracker.get_performance_records(date_range)
        team_records = [
            rec for rec in all_records 
            if rec.get("fields", {}).get("team", [{}])[0].get("text", "") == team_name
        ]
        return team_records

    def _get_user_records(self, email: str, date_range: tuple) -> List[Dict]:
        """Get performance records for specific user by campaign_manager email"""
        all_records = self.tracker.get_performance_records(date_range)
        user_records = [
            rec for rec in all_records 
            if rec.get("fields", {}).get("campaign_manager", [{}])[0].get("text", "").lower() == email.lower()
        ]
        return user_records

    def _aggregate_performance(self, records: List[Dict]) -> Dict[str, Any]:
        """Aggregate performance metrics from records"""
        total_spend = 0
        total_revenue = 0
        total_profit = 0
        record_count = 0
        
        for record in records:
            fields = record.get("fields", {})
            spend = float(fields.get("spend", [0])[0].get("number", 0))
            revenue = float(fields.get("revenue", [0])[0].get("number", 0))
            
            total_spend += spend
            total_revenue += revenue
            total_profit += (revenue - spend)
            record_count += 1
        
        return {
            "records": record_count,
            "spend": total_spend,
            "revenue": total_revenue,
            "profit": total_profit,
            "roas": total_revenue / total_spend if total_spend > 0 else 0
        }

    def _format_performance_message(self, team_name: str, date_range: tuple, records: List[Dict]) -> str:
        """Format performance message for display"""
        start_date, end_date = date_range
        
        if not records:
            return f"📊 **{team_name} - {start_date} to {end_date}**\n\nNo performance data found for this period."
        
        agg = self._aggregate_performance(records)
        
        message = f"📊 **{team_name} - {start_date} to {end_date}**\n\n"
        message += f"**Records:** {agg['records']}\n"
        message += f"**Spend:** ${agg['spend']:,.0f}\n"
        message += f"**Revenue:** ${agg['revenue']:,.0f}\n"
        message += f"**Profit:** ${agg['profit']:,.0f}\n"
        message += f"**ROAS:** {agg['roas']:.2f}x\n\n"
        
        return message

    def handle_performance_command(self, text: str, user_open_id: str) -> str:
        """Main command handler"""
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
            all_records = self.tracker.get_performance_records(date_range)
            return self._format_performance_message("All Teams", date_range, all_records)
        
        # Personal performance ("perf me")
        elif command_type == "me":
            # Find user's email from user_data or use open_id lookup
            user_email = self._find_user_email(user_open_id)
            if user_email:
                records = self._get_user_records(user_email, date_range)
                user_name = self.user_data.get(user_email.lower(), {}).get("name", "You")
                return self._format_performance_message(f"{user_name}'s Performance", date_range, records)
            return "❌ Could not find your performance data."
        
        # Email-based user lookup (perf amanda.g@intentt.com)
        elif "@" in command_type:
            records = self._get_user_records(command_type, date_range)
            return self._format_performance_message(f"{command_type}'s Performance", date_range, records)
        
        return self._get_help_text()

    def _find_user_email(self, user_open_id: str) -> str:
        """Find user email by lark_user_key"""
        for email, data in self.user_data.items():
            if data.get("lark_user_key") == user_open_id:
                return email
        return None

    def _get_help_text(self) -> str:
        """Help text for performance commands"""
        return """📊 **Performance Command Help**

**View Your Performance:**
• `perf me` - Today
• `perf me yesterday` - Yesterday only  
• `perf me last 7` - Last 7 days
• `perf me mtd` - Month to date (1st to today)

**View All Teams:**
• `perf team` - Today
• `perf team yesterday` - Yesterday only
• `perf team last 7` - Last 7 days
• `perf team mtd` - Month to date

**View Specific Team (with individual breakdown):**
• `perf amanda` - Amanda's Team today
• `perf amanda yesterday` - Yesterday only
• `perf amanda last 7` - Last 7 days
• `perf amanda mtd` - Month to date
• `perf dioulde`, `perf kath`, `perf jello` - Other teams

**Manager - View Specific Person:**
• `perf amanda.g@intentt.com` - Today
• `perf amanda.g@intentt.com yesterday` - Yesterday
• `perf amanda.g@intentt.com last 7` - Last 7 days
• `perf amanda.g@intentt.com mtd` - Month to date

**Examples:**
perf me
perf me mtd
perf team last 7
perf amanda mtd
perf amanda.g@intentt.com last 7"""

