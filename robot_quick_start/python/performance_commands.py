"""
Performance Commands Handler for Lark Bot
Handles all performance tracking queries (perf, perf team, etc.)
"""

from datetime import datetime, timedelta
import pytz


class PerformanceCommands:
    """Handler for performance-related commands"""
    
    def __init__(self, tracker, user_data=None):
        """
        Initialize PerformanceCommands handler
        
        Args:
            tracker: MeetingTracker instance for accessing data
            user_data: Optional user data dictionary for caching
        """
        self.tracker = tracker
        self.user_data = user_data or {}
        self.montreal_tz = pytz.timezone('America/Toronto')
    
    def handle_performance_command(self, text: str, user_open_id: str):
        """
        Main handler for performance commands
        
        ✅ FIXED: Proper team command parsing with correct indices
        ✅ FIXED: Actual date range tracking
        
        Args:
            text: Command text (e.g., "perf jonas last 7 days" or "perf team amanda last 7 days")
            user_open_id: Lark user ID who sent command
        
        Returns:
            Response message
        """
        # Parse command
        parts = text.lower().strip().split()
        if not parts or parts[0] != "perf":
            return "❌ Invalid command"
        
        # Get command parts
        if len(parts) == 1:
            # Just "perf"
            return "❌ Use: perf me, perf team, perf [name], etc. Type 'perf help' for options."
        
        # ✅ FIXED: Use offset approach instead of modifying parts array
        is_team_command = False
        command_start = 1  # Index where command actually starts (after "perf")
        
        if len(parts) >= 2 and parts[1] == "team":
            is_team_command = True
            command_start = 2  # Skip both "perf" and "team"
        
        print(f"DEBUG: Is team command: {is_team_command}, Command starts at index: {command_start}")
        print(f"DEBUG: Parts: {parts}")
        
        # Parse date range (default: last 7 days)
        date_range = "last 7 days"
        search_target = None
        
        # Find where date range starts (if any)
        # Start from command_start to find the first date keyword
        date_keywords = ["yesterday", "today", "last", "mtd", "month"]
        date_start_idx = None
        
        for i, part in enumerate(parts[command_start:], start=command_start):
            if part in date_keywords:
                date_start_idx = i
                break
        
        print(f"DEBUG: date_start_idx: {date_start_idx}")
        
        if date_start_idx:
            # Extract search target: everything between command_start and date_start_idx
            search_target = " ".join(parts[command_start:date_start_idx]).strip()
            # Extract date range: everything from date_start_idx onward
            date_range = " ".join(parts[date_start_idx:]).strip()
        else:
            # No date keywords found, use everything after command_start as search_target
            search_target = " ".join(parts[command_start:]).strip() if len(parts) > command_start else None
        
        print(f"DEBUG: search_target: '{search_target}', date_range: '{date_range}'")
        
        # ✅ UPDATED: Use Montreal EST timezone
        start_date, end_date = self._get_montreal_dates(date_range)
        
        print(f"DEBUG: Fetching performance data for {start_date} to {end_date}")
        
        # Handle different command types
        if not search_target or search_target == "help":
            return self._get_help_text()
        elif search_target == "me":
            return "❌ Can't determine your email. Contact admin to register."
        elif search_target == "team" and not is_team_command:
            # Show all team performance (perf team without name)
            print(f"DEBUG: Showing all teams performance")
            return self._get_team_performance(None, start_date, end_date)
        elif is_team_command:
            # ✅ NEW: Handle "perf team [name]" command
            print(f"DEBUG: Showing specific team '{search_target}' performance")
            return self._get_team_performance(search_target, start_date, end_date)
        else:
            # Show individual performance
            print(f"DEBUG: Showing individual '{search_target}' performance")
            return self._get_individual_performance(search_target, start_date, end_date)
    
    def _get_montreal_dates(self, date_range: str):
        """
        Calculate date range in Montreal EST timezone
        
        Args:
            date_range: String like "last 7 days", "yesterday", "mtd", "month"
        
        Returns:
            Tuple of (start_date, end_date) as strings "YYYY-MM-DD"
        """
        # Get current time in Montreal timezone
        now = datetime.now(self.montreal_tz)
        today = now.date()
        
        date_range_lower = date_range.lower().strip()
        
        if "yesterday" in date_range_lower:
            yesterday = today - timedelta(days=1)
            return yesterday.isoformat(), yesterday.isoformat()
        
        elif "today" in date_range_lower:
            return today.isoformat(), today.isoformat()
        
        elif "mtd" in date_range_lower or "month to date" in date_range_lower:
            # Month to date: from 1st of current month to today
            month_start = today.replace(day=1)
            return month_start.isoformat(), today.isoformat()
        
        elif "month" in date_range_lower:
            # Last month
            first_of_this_month = today.replace(day=1)
            last_of_prev_month = first_of_this_month - timedelta(days=1)
            first_of_prev_month = last_of_prev_month.replace(day=1)
            return first_of_prev_month.isoformat(), last_of_prev_month.isoformat()
        
        elif "last" in date_range_lower:
            # Parse "last X days"
            try:
                parts = date_range_lower.split()
                if len(parts) >= 2:
                    days = int(parts[1])
                    start = today - timedelta(days=days-1)  # Inclusive of today
                    return start.isoformat(), today.isoformat()
            except (ValueError, IndexError):
                pass
        
        # Default: last 7 days
        start = today - timedelta(days=6)
        return start.isoformat(), today.isoformat()
    
    def _get_individual_performance(self, name: str, start_date: str, end_date: str):
        """
        Get performance stats for an individual media buyer
        
        Args:
            name: Name to search for (e.g., "jonas", "amanda")
            start_date: Start date as "YYYY-MM-DD"
            end_date: End date as "YYYY-MM-DD"
        
        Returns:
            Performance summary message
        """
        if not name or name.lower() in ["", "all", "team"]:
            return self._get_team_performance(None, start_date, end_date)
        
        try:
            # Get performance data for this individual
            metrics = self._get_performance_batch(
                search_term=name,
                start_date=start_date,
                end_date=end_date,
                is_team=False
            )
            
            if not metrics or metrics.get("count", 0) == 0:
                return f"❌ No data found for '{name}' between {start_date} and {end_date}"
            
            # Format response
            revenue = metrics.get("revenue", 0)
            spend = metrics.get("spend", 0)
            profit = revenue - spend
            roi = (profit / spend * 100) if spend > 0 else 0
            days = metrics.get("days", 0)
            
            actual_start = metrics.get("min_date", start_date)
            actual_end = metrics.get("max_date", end_date)
            team_name = metrics.get("team_name", "Unknown Team")
            
            return (
                f"❌ **{name.title()}** ({team_name}) - Performance ({actual_start} to {actual_end})\n"
                f"Revenue: ${revenue:,.0f}\n"
                f"Spend: ${spend:,.0f}\n"
                f"Profit: ${profit:,.0f}\n"
                f"ROI: {roi:.1f}%\n"
                f"Days: {days}"
            )
        
        except Exception as e:
            print(f"ERROR in _get_individual_performance: {e}")
            return f"❌ Error fetching performance for '{name}': {str(e)}"
    
    def _get_team_performance(self, team_name: str, start_date: str, end_date: str):
        """
        Get performance stats for a team or all teams
        
        Args:
            team_name: Team name to search for (None for all teams)
            start_date: Start date as "YYYY-MM-DD"
            end_date: End date as "YYYY-MM-DD"
        
        Returns:
            Team performance summary message
        """
        try:
            if team_name:
                # Get performance for specific team
                print(f"DEBUG: Fetching specific team '{team_name}' performance")
                metrics = self._get_performance_batch(
                    search_term=team_name,
                    start_date=start_date,
                    end_date=end_date,
                    is_team=True
                )
                
                if not metrics or metrics.get("count", 0) == 0:
                    return f"❌ No data found for team '{team_name}' between {start_date} and {end_date}"
                
                revenue = metrics.get("revenue", 0)
                spend = metrics.get("spend", 0)
                profit = revenue - spend
                roi = (profit / spend * 100) if spend > 0 else 0
                actual_start = metrics.get("min_date", start_date)
                actual_end = metrics.get("max_date", end_date)
                
                return (
                    f"✅ **{team_name.title()}'s Team** - Performance ({actual_start} to {actual_end})\n"
                    f"Revenue: ${revenue:,.0f}\n"
                    f"Spend: ${spend:,.0f}\n"
                    f"Profit: ${profit:,.0f}\n"
                    f"ROI: {roi:.1f}%"
                )
            
            else:
                # Get performance for all teams
                print(f"DEBUG: Fetching all teams performance")
                all_teams = self._get_all_teams_performance(start_date, end_date)
                
                if not all_teams:
                    return f"❌ No team data found between {start_date} and {end_date}"
                
                response = f"📊 **Team Performance Summary** ({start_date} to {end_date})\n\n"
                
                for team in all_teams:
                    team_name = team.get("name", "Unknown")
                    revenue = team.get("revenue", 0)
                    spend = team.get("spend", 0)
                    profit = revenue - spend
                    roi = (profit / spend * 100) if spend > 0 else 0
                    actual_start = team.get("min_date", start_date)
                    actual_end = team.get("max_date", end_date)
                    
                    status = "✅" if profit >= 0 else "❌"
                    response += (
                        f"{status} **{team_name}** ({actual_start} to {actual_end})\n"
                        f"   Revenue: ${revenue:,.0f} | Spend: ${spend:,.0f} | "
                        f"Profit: ${profit:,.0f} (ROI: {roi:.1f}%)\n\n"
                    )
                
                return response.strip()
        
        except Exception as e:
            print(f"ERROR in _get_team_performance: {e}")
            return f"❌ Error fetching team performance: {str(e)}"
    
    def _get_performance_batch(self, search_term: str, start_date: str, end_date: str, is_team: bool):
        """
        Fetch performance metrics from Lark Base
        
        ✅ FIXED: Tracks actual min_date and max_date from records
        
        Args:
            search_term: Name to search for
            start_date: Start date as "YYYY-MM-DD"
            end_date: End date as "YYYY-MM-DD"
            is_team: Whether searching for team or individual
        
        Returns:
            Dictionary with metrics (revenue, spend, min_date, max_date, etc.)
        """
        try:
            # Get records from Lark Base
            # This assumes tracker.client has methods to query Lark Base
            records = self.tracker.client.get_performance_records(
                search_term=search_term,
                start_date=start_date,
                end_date=end_date,
                is_team=is_team
            )
            
            if not records:
                print(f"DEBUG: No records found for {search_term}")
                return {"count": 0, "revenue": 0, "spend": 0}
            
            print(f"DEBUG: Looking for {len(records)} users in {len(records)} records")
            
            # ✅ FIXED: Track actual min/max dates from records
            min_date = None
            max_date = None
            total_revenue = 0
            total_spend = 0
            matched_count = 0
            
            for record in records:
                # Extract date from record
                # Adjust field names based on your Lark Base schema
                date_field = record.get("date") or record.get("Date") or record.get("created_at")
                
                record_date = self.tracker.client._extract_date_string(date_field)
                if record_date:
                    if min_date is None or record_date < min_date:
                        min_date = record_date
                    if max_date is None or record_date > max_date:
                        max_date = record_date
                
                # Sum metrics
                revenue = record.get("revenue", 0) or 0
                spend = record.get("spend", 0) or 0
                total_revenue += revenue
                total_spend += spend
                matched_count += 1
            
            print(f"DEBUG: Matched {matched_count} records")
            
            result = {
                "count": matched_count,
                "revenue": total_revenue,
                "spend": total_spend,
                "min_date": min_date or start_date,
                "max_date": max_date or end_date,
                "days": (datetime.fromisoformat(max_date or end_date) - 
                        datetime.fromisoformat(min_date or start_date)).days + 1
            }
            
            return result
        
        except Exception as e:
            print(f"ERROR in _get_performance_batch: {e}")
            return {"count": 0, "revenue": 0, "spend": 0}
    
    def _get_all_teams_performance(self, start_date: str, end_date: str):
        """
        Get performance for all teams
        
        Args:
            start_date: Start date as "YYYY-MM-DD"
            end_date: End date as "YYYY-MM-DD"
        
        Returns:
            List of team performance dictionaries
        """
        try:
            # Define your teams here
            teams = [
                "Amanda's Team",
                "Kath's Team",
                "Team 3",
                "Team 4"
            ]
            
            all_teams_data = []
            
            for team in teams:
                metrics = self._get_performance_batch(
                    search_term=team,
                    start_date=start_date,
                    end_date=end_date,
                    is_team=True
                )
                
                if metrics.get("count", 0) > 0:
                    all_teams_data.append({
                        "name": team,
                        "revenue": metrics.get("revenue", 0),
                        "spend": metrics.get("spend", 0),
                        "min_date": metrics.get("min_date", start_date),
                        "max_date": metrics.get("max_date", end_date)
                    })
            
            return all_teams_data
        
        except Exception as e:
            print(f"ERROR in _get_all_teams_performance: {e}")
            return []
    
    def _get_help_text(self):
        """Return help text for performance commands"""
        return (
            "📊 **Performance Commands Help**\n\n"
            "**Individual Performance:**\n"
            "  `perf [name] [date_range]` - Get individual stats\n"
            "  Examples:\n"
            "    • perf amanda\n"
            "    • perf jonas last 7 days\n"
            "    • perf sarah yesterday\n\n"
            "**Team Performance:**\n"
            "  `perf team [name] [date_range]` - Get team stats\n"
            "  Examples:\n"
            "    • perf team amanda\n"
            "    • perf team kath last 7 days\n"
            "    • perf team last 30 days\n\n"
            "**All Teams:**\n"
            "  `perf team [date_range]` - Get all teams stats\n"
            "  Examples:\n"
            "    • perf team\n"
            "    • perf team last 7 days\n"
            "    • perf team mtd\n\n"
            "**Date Ranges:**\n"
            "  • `last X days` (default: 7)\n"
            "  • `yesterday`\n"
            "  • `today`\n"
            "  • `mtd` (month to date)\n"
            "  • `month` (last month)"
        )
