"""
Performance Commands Handler for Lark Bot
Handles all performance tracking queries (perf, perf team, etc.)
"""


from datetime import datetime, timedelta
import pytz



class PerformanceCommands:
    """Handler for performance-related commands"""
    
    def __init__(self, performance_tracker, user_data: dict):
        """
        Initialize PerformanceCommands handler
        
        Args:
            performance_tracker: PerformanceTracker instance
            user_data: Dictionary of users keyed by email
        """
        self.tracker = performance_tracker
        self.user_data = user_data
        self.montreal_tz = pytz.timezone('America/Toronto')
        
        # ✅ Team mapping from Lark Base formula
        self.team_mapping = {
            "amanda.g@intentt.com": "Amanda's Team",
            "jonas.f@intentt.com": "Amanda's Team",
            "brent.l@intentt.com": "Amanda's Team",
            "kath.g@intentt.com": "Kath's Team",
            "angelika.m@intentt.com": "Kath's Team",
            "dioulde.n@intentt.com": "Dioulde's Team",
            "rachel.l@intentt.com": "Dioulde's Team",
            "jello.c@intentt.com": "Jello's Team",
            "job.c@intentt.com": "Kath's Team",
        }
    
    def handle_performance_command(self, text: str, user_open_id: str):
        """
        Main handler for performance commands
        
        Args:
            text: Command text (e.g., "perf jonas last 7 days" or "perf team dioulde last 7 days")
            user_open_id: Lark user ID who sent command
        
        Returns:
            Response message
        """
        # Parse command
        parts = text.lower().strip().split()
        if not parts or parts[0] != "perf":
            return "❌ Invalid command"
        
        if len(parts) == 1:
            return "❌ Use: perf me, perf team, perf [name], etc. Type 'perf help' for options."
        
        is_team_command = False
        command_start = 1
        
        if len(parts) >= 2 and parts[1] == "team":
            is_team_command = True
            command_start = 2
        
        print(f"DEBUG: Is team command: {is_team_command}, Command starts at index: {command_start}")
        print(f"DEBUG: Parts: {parts}")
        
        date_range = "last 7 days"
        search_target = None
        
        date_keywords = ["yesterday", "today", "last", "mtd", "month"]
        date_start_idx = None
        
        for i, part in enumerate(parts[command_start:], start=command_start):
            if part in date_keywords:
                date_start_idx = i
                break
        
        print(f"DEBUG: date_start_idx: {date_start_idx}")
        
        if date_start_idx:
            search_target = " ".join(parts[command_start:date_start_idx]).strip()
            date_range = " ".join(parts[date_start_idx:]).strip()
        else:
            search_target = " ".join(parts[command_start:]).strip() if len(parts) > command_start else None
        
        print(f"DEBUG: search_target: '{search_target}', date_range: '{date_range}'")
        
        # ✅ FIXED: Now returns 3 values instead of 2
        start_date, display_end_date, api_end_date = self._get_montreal_dates(date_range)
        
        print(f"DEBUG: Fetching performance data for {start_date} to {api_end_date} (display: {start_date} to {display_end_date})")
        
        if search_target == "help":
            return self._get_help_text()
        elif search_target == "me":
            return "❌ Can't determine your email. Contact admin to register."
        elif is_team_command:
            if not search_target or search_target == "":
                print("DEBUG: Routing to all teams (perf team with empty search_target)")
                return self._get_team_performance(None, start_date, display_end_date, api_end_date)
            else:
                print(f"DEBUG: Routing to specific team '{search_target}'")
                return self._get_team_performance(search_target, start_date, display_end_date, api_end_date)
        elif not search_target:
            return self._get_help_text()
        else:
            print(f"DEBUG: Showing individual '{search_target}' performance")
            return self._get_individual_performance(search_target, start_date, display_end_date, api_end_date)
    
    def _get_montreal_dates(self, date_range: str):
        """
        Calculate date range in Montreal EST timezone
        
        Args:
            date_range: String like "last 7 days", "yesterday", "mtd", "month"
        
        Returns:
            Tuple of (start_date, display_end_date, api_end_date) as strings "YYYY-MM-DD"
            - start_date: First day to include
            - display_end_date: Last day to DISPLAY (what was requested)
            - api_end_date: Last day for API query (one day after display_end_date)
        """
        now = datetime.now(self.montreal_tz)
        today = now.date()
        
        date_range_lower = date_range.lower().strip()
        
        if "yesterday" in date_range_lower:
            yesterday = today - timedelta(days=1)
            api_end = today  # Tomorrow is today
            return yesterday.isoformat(), yesterday.isoformat(), api_end.isoformat()
        
        elif "today" in date_range_lower:
            api_end = today + timedelta(days=1)  # Tomorrow
            return today.isoformat(), today.isoformat(), api_end.isoformat()
        
        elif "mtd" in date_range_lower or "month to date" in date_range_lower:
            month_start = today.replace(day=1)
            yesterday = today - timedelta(days=1)  # Display up to yesterday
            api_end = today  # API query includes today
            return month_start.isoformat(), yesterday.isoformat(), api_end.isoformat()
        
        elif "month" in date_range_lower:
            first_of_this_month = today.replace(day=1)
            last_of_prev_month = first_of_this_month - timedelta(days=1)
            first_of_prev_month = last_of_prev_month.replace(day=1)
            api_end = last_of_prev_month + timedelta(days=1)
            return first_of_prev_month.isoformat(), last_of_prev_month.isoformat(), api_end.isoformat()
        
        elif "last" in date_range_lower:
            try:
                parts = date_range_lower.split()
                if len(parts) >= 2:
                    days = int(parts[1])
                    # ✅ FIXED: Properly separate display_end and api_end
                    display_end = today - timedelta(days=1)  # Yesterday (what to display)
                    start = display_end - timedelta(days=days-1)  # X days total
                    api_end = display_end + timedelta(days=1)  # Tomorrow (for API query)
                    return start.isoformat(), display_end.isoformat(), api_end.isoformat()
            except (ValueError, IndexError):
                pass
        
        # ✅ FIXED: Default to last 7 days excluding today
        display_end = today - timedelta(days=1)  # Yesterday
        start = display_end - timedelta(days=6)  # 7 days total
        api_end = display_end + timedelta(days=1)  # Tomorrow
        return start.isoformat(), display_end.isoformat(), api_end.isoformat()
    
    def _find_user_by_email_or_name(self, target: str):
        """
        Find user by exact email or partial name match (case-insensitive)
        
        Args:
            target: Email or name to search for
        
        Returns:
            Tuple of (email, user_info) or (None, None) if not found
        """
        target_lower = target.lower()
        
        if target_lower in self.user_data:
            return target_lower, self.user_data[target_lower]
        
        for email, info in self.user_data.items():
            name = info.get("name", "").lower()
            if target_lower in name:
                return email, info
        
        return None, None
    
    def _get_media_buyers_by_department(self):
        """Get all media_buying users"""
        return [
            (email, info) for email, info in self.user_data.items()
            if "media_buying" in info.get("department", "").lower()
        ]
    
    def _get_performance_batch(self, emails: list, start_date: str, api_end_date: str):
        """
        Get performance metrics for multiple users across date range
        
        Args:
            emails: List of email addresses (lowercase)
            start_date: Start date (YYYY-MM-DD)
            api_end_date: End date for API query (YYYY-MM-DD)
        
        Returns:
            Tuple of (perf_by_email, actual_min_date, actual_max_date)
            - perf_by_email: Dictionary with performance data by email
            - actual_min_date: Actual minimum date found in data (or None)
            - actual_max_date: Actual maximum date found in data (or None)
        """
        records = self.tracker.client.get_performance_records(start_date, api_end_date)
        
        actual_dates_found = set()
        for record in records:
            fields = record.get("fields", {})
            date_field = fields.get("date")
            if date_field:
                record_date = self.tracker.client._extract_date_string(date_field)
                if record_date:
                    actual_dates_found.add(record_date)
        
        print(f"DEBUG: Received {len(records)} total records from API")
        print(f"DEBUG DATES: Actual dates in filtered records: {sorted(actual_dates_found)}")
        print(f"DEBUG DATES: API query range: {start_date} to {api_end_date}")
        
        emails_lower = [e.lower() for e in emails]
        
        perf_by_email = {}
        for email in emails_lower:
            perf_by_email[email] = {"revenue": 0, "spend": 0, "profit": 0, "days_with_data": 0}
        
        print(f"DEBUG: Looking for {len(emails_lower)} users in {len(records)} records")
        print(f"DEBUG: Users to match: {emails_lower}")
        
        matched_count = 0
        
        for record in records:
            fields = record.get("fields", {})
            campaign_manager_field = fields.get("campaign_manager", "")
            
            manager_email = self.tracker.client._extract_email_from_field(campaign_manager_field)
            
            manager_email_lower = manager_email.lower() if manager_email else ""
            
            if not manager_email_lower:
                continue
            
            if manager_email_lower in emails_lower:
                matched_count += 1
                try:
                    revenue = float(fields.get("revenue", 0) or 0)
                    spend = float(fields.get("spend", 0) or 0)
                    profit = float(fields.get("profit", 0) or 0)
                    
                    perf_by_email[manager_email_lower]["revenue"] += revenue
                    perf_by_email[manager_email_lower]["spend"] += spend
                    perf_by_email[manager_email_lower]["profit"] += profit
                    perf_by_email[manager_email_lower]["days_with_data"] += 1
                except (ValueError, TypeError):
                    continue
        
        print(f"DEBUG: Matched {matched_count} records for {len([e for e in perf_by_email.values() if e['days_with_data'] > 0])} users")
        
        # ✅ NEW: Calculate actual min/max dates from data
        if actual_dates_found:
            actual_min_date = min(actual_dates_found)
            actual_max_date = max(actual_dates_found)
        else:
            actual_min_date = None
            actual_max_date = None
        
        return perf_by_email, actual_min_date, actual_max_date
    
    def _get_individual_performance(self, name: str, start_date: str, display_end_date: str, api_end_date: str):
        """
        Get performance stats for an individual media buyer
        
        Args:
            name: Name to search for (e.g., "jonas", "amanda")
            start_date: Start date as "YYYY-MM-DD"
            display_end_date: End date to display as "YYYY-MM-DD"
            api_end_date: End date for API query as "YYYY-MM-DD"
        
        Returns:
            Performance summary message
        """
        if not name or name.lower() in ["", "all", "team"]:
            return self._get_team_performance(None, start_date, display_end_date, api_end_date)
        
        try:
            email, user_info = self._find_user_by_email_or_name(name)
            if not email:
                return f"❌ User '{name}' not found in system"
            
            if "media_buying" not in user_info.get("department", "").lower():
                return f"❌ No performance data for {user_info['name']} (not a media buyer)"
            
            # ✅ NEW: Unpack 3 values including actual dates
            perf, actual_min_date, actual_max_date = self._get_performance_batch([email], start_date, api_end_date)
            
            email_lower = email.lower()
            
            if email_lower not in perf or perf[email_lower]["days_with_data"] == 0:
                return f"❌ No data found for '{name}' between {start_date} and {display_end_date}"
            
            metrics = perf[email_lower]
            total_revenue = metrics["revenue"]
            total_spend = metrics["spend"]
            total_profit = metrics["profit"]
            roi = (total_profit / total_spend * 100) if total_spend > 0 else 0
            
            status = "✅" if roi >= 20 else "⚠️" if roi >= 10 else "❌"
            
            team_name = self.team_mapping.get(email_lower, "Unknown Team")
            
            # ✅ FIXED: Use actual dates from data (no +1 day shift needed!)
            if actual_min_date and actual_max_date:
                date_range_display = f"({actual_min_date} to {actual_max_date})"
            else:
                date_range_display = f"({start_date} to {display_end_date})"
            
            return (
                f"{status} **{user_info['name']}** ({team_name}) - Performance {date_range_display}\n"
                f"Revenue: ${total_revenue:,.0f}\n"
                f"Spend: ${total_spend:,.0f}\n"
                f"Profit: ${total_profit:,.0f}\n"
                f"ROI: {roi:.1f}%\n"
                f"Days: {metrics['days_with_data']}"
            )
        
        except Exception as e:
            print(f"ERROR in _get_individual_performance: {e}")
            return f"❌ Error fetching performance for '{name}': {str(e)}"
    
    def _get_team_performance(self, team_name: str, start_date: str, display_end_date: str, api_end_date: str):
        """
        Get performance stats for a team or all teams
        
        Args:
            team_name: Team name to search for (None for all teams)
            start_date: Start date as "YYYY-MM-DD"
            display_end_date: End date to display as "YYYY-MM-DD"
            api_end_date: End date for API query as "YYYY-MM-DD"
        
        Returns:
            Team performance summary message
        """
        try:
            media_buyers = self._get_media_buyers_by_department()
            
            if not media_buyers:
                return "❌ No media buyers found"
            
            emails = [email for email, _ in media_buyers]
            # ✅ NEW: Unpack 3 values including actual dates
            perf, actual_min_date, actual_max_date = self._get_performance_batch(emails, start_date, api_end_date)
            
            if team_name:
                print(f"DEBUG: Fetching specific team '{team_name}' performance")
                
                team_emails = []
                actual_team_name = None
                
                # First try exact team name match
                for email, team in self.team_mapping.items():
                    if team.lower() == team_name.lower():
                        team_emails.append(email)
                        actual_team_name = team
                        break
                
                # If no exact match, try leader name match
                if not team_emails:
                    for email, team in self.team_mapping.items():
                        leader_name = team.split("'")[0].lower()
                        if leader_name == team_name.lower():
                            actual_team_name = team
                            for e, t in self.team_mapping.items():
                                if t == team:
                                    team_emails.append(e)
                            break
                
                print(f"DEBUG: Found {len(team_emails)} team members for '{team_name}' -> '{actual_team_name}'")
                
                if not team_emails:
                    return f"❌ Team '{team_name}' not found. Try: amanda, kath, dioulde, jello"
                
                team_revenue = 0
                team_spend = 0
                team_profit = 0
                team_members_with_data = 0
                
                for email in team_emails:
                    email_lower = email.lower()
                    if email_lower in perf and perf[email_lower]["days_with_data"] > 0:
                        team_revenue += perf[email_lower]["revenue"]
                        team_spend += perf[email_lower]["spend"]
                        team_profit += perf[email_lower]["profit"]
                        team_members_with_data += 1
                
                if team_members_with_data == 0:
                    return f"❌ No data found for team '{actual_team_name or team_name}' between {start_date} and {display_end_date}"
                
                roi = (team_profit / team_spend * 100) if team_spend > 0 else 0
                status = "✅" if team_profit >= 0 else "❌"
                
                display_team_name = actual_team_name or team_name
                
                # ✅ FIXED: Use actual dates from data (no +1 day shift needed!)
                if actual_min_date and actual_max_date:
                    date_range_display = f"({actual_min_date} to {actual_max_date})"
                else:
                    date_range_display = f"({start_date} to {display_end_date})"
                
                return (
                    f"{status} **{display_team_name}** - Performance {date_range_display}\n"
                    f"Revenue: ${team_revenue:,.0f}\n"
                    f"Spend: ${team_spend:,.0f}\n"
                    f"Profit: ${team_profit:,.0f}\n"
                    f"ROI: {roi:.1f}%\n"
                    f"Members with data: {team_members_with_data}"
                )
            
            else:
                print(f"DEBUG: Fetching all teams performance")
                
                teams_data = {}
                
                for email, metrics in perf.items():
                    team_name = self.team_mapping.get(email, "Unknown Team")
                    if team_name not in teams_data:
                        teams_data[team_name] = {"revenue": 0, "spend": 0, "profit": 0}
                    
                    if metrics["days_with_data"] > 0:
                        teams_data[team_name]["revenue"] += metrics["revenue"]
                        teams_data[team_name]["spend"] += metrics["spend"]
                        teams_data[team_name]["profit"] += metrics["profit"]
                
                if not teams_data:
                    return f"❌ No team data found between {start_date} and {display_end_date}"
                
                # ✅ FIXED: Use actual dates from data (no +1 day shift needed!)
                if actual_min_date and actual_max_date:
                    date_range_display = f"({actual_min_date} to {actual_max_date})"
                else:
                    date_range_display = f"({start_date} to {display_end_date})"
                
                response = f"📊 **Team Performance Summary** {date_range_display}\n\n"
                
                for team_name, data in sorted(teams_data.items()):
                    roi = (data["profit"] / data["spend"] * 100) if data["spend"] > 0 else 0
                    status = "✅" if data["profit"] > 0 else "❌"
                    response += (
                        f"{status} **{team_name}**\n"
                        f"   Revenue: ${data['revenue']:,.0f} | Spend: ${data['spend']:,.0f} | "
                        f"Profit: ${data['profit']:,.0f} (ROI: {roi:.1f}%)\n\n"
                    )
                
                return response.strip()
        
        except Exception as e:
            print(f"ERROR in _get_team_performance: {e}")
            return f"❌ Error fetching team performance: {str(e)}"
    
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
            "    • perf team dioulde\n\n"
            "**All Teams:**\n"
            "  `perf team [date_range]` - Get all teams stats\n"
            "  Examples:\n"
            "    • perf team\n"
            "    • perf team last 7 days\n"
            "    • perf team mtd\n\n"
            "**Date Ranges:**\n"
            "  • `last X days` (excludes today)\n"
            "  • `yesterday`\n"
            "  • `today`\n"
            "  • `mtd` (month to date, excludes today)\n"
            "  • `month` (last month)\n\n"
            "⏰ All times in **Montreal EST**\n"
            "📅 Date ranges shown match actual data available"
        )
