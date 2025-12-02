from datetime import datetime, timedelta
from typing import Dict, List, Any
from lark_base_client import PerformanceTracker

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
        """Get performance records for specific team using team formula field"""
        all_records = self.performance_tracker.get_performance_records(date_range)
        team_records = []
        
        for record in all_records:
            fields = record.get("fields", {})
            # Handle both formula field structure and simple text
            team_field = fields.get("team", {})
            if isinstance(team_field, dict) and "value" in team_field:
                team_text = team_field["value"][0].get("text", "") if team_field["value"] else ""
            else:
                team_text = str(team_field).lower()
            
            if team_name.lower() in team_text.lower():
                team_records.append(record)
        
        return team_records

    def _aggregate_performance(self, records: List[Dict]) -> Dict[str, Any]:
        """Aggregate performance metrics from records"""
        total_spend = 0
        total_revenue = 0
        total_profit = 0
        record_count = 0
        
        for record in records:
            fields = record.get("fields", {})
            
            # Handle number fields safely
            spend = float(fields.get("spend", 0) or 0)
            revenue = float(fields.get("revenue", 0) or 0)
            profit = float(fields.get("profit", 0) or 0)
            
            total_spend += spend
            total_revenue += revenue
            total_profit += profit
            record_count += 1
        
        return {
            "records": record_count,
            "spend": total_spend,
            "revenue": total_revenue,
            "profit": total_profit,
            "roas": total_revenue / total_spend if total_spend > 0 else 0
        }

    def _format_performance_message(self, title: str, date_range: tuple, records: List[Dict]) -> str:
        """Format performance message for display"""
        start_date, end_date = date_range
        
        if not records:
            return f"📊 **{title} - {start_date} to {end_date}**\n\nNo performance data found for this period."
        
        agg = self._aggregate_performance(records)
        
        message = f"📊 **{title} - {start_date} to {end_date}**\n\n"
        message += f"**Records:** {agg['records']}\n"
        message += f"**Spend:** ${agg['spend']:,.0f}\n"
        message += f"**Revenue:** ${agg['revenue']:,.0f}\n"
        message += f"**Profit:** ${agg['profit']:,.0f}\n"
        message += f"**ROAS:** {agg['roas']:.2f}x\n"
        
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
            records = self.performance_tracker.get_performance_records(date_range)
            return self._format_performance_message("All Teams", date_range, records)
        
        # Personal performance ("perf me")
        elif command_type == "me":
            # Simple fallback for now
            records = self.performance_tracker.get_performance_records(date_range)
            return self._format_performance_message("Your Performance", date_range, records)
        
        # Email-based user lookup
        elif "@" in command_type:
            records = self.performance_tracker.get_performance_records(date_range)
            return self._format_performance_message(f"{command_type}'s Performance", date_range, records)
        
        return self._get_help_text()

    def _get_help_text(self) -> str:
        """Help text for performance commands"""
        return """📊 **Performance Command Help**

**View Your Performance:**
• `perf me` - Today
• `perf me yesterday` - Yesterday only
• `perf me last 7` - Last 7 days
• `perf me mtd` - Month to date

**View All Teams:**
• `perf team` - Today
• `perf team yesterday` - Yesterday only
• `perf team last 7` - Last 7 days
• `perf team mtd` - Month to date

**View Specific Team:**
• `perf amanda` - Amanda's Team today
• `perf amanda yesterday` - Yesterday only
• `perf dioulde`, `perf kath`, `perf jello`

**Examples:**
perf me
perf team last 7
perf amanda mtd"""

