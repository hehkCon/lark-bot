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
            "job.c@intentt.com": "Jello's Team",
        }
    
    def handle_performance_command(self, text: str, user_open_id: str):
        """
        Main handler for performance commands
        
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
        
        # ✅ FIXED: Handle all 3 issues
        if not search_target or search_target == "help":
            return self._get_help_text()
        elif search_target == "me":
            return "❌ Can't determine your email. Contact admin to register."
        elif is_team_command and (not search_target or search_target.lower() == "none"):
            # perf team → all teams
            print("DEBUG: Showing ALL teams performance (perf team)")
            return self._get_team_performance(None, start_date, end_date)
        elif is_team_command:
            # perf team [name] → specific leader's team
            print(f"DEBUG: Showing specific team '{search_target}' performance")
            return self._get_team_performance(search_target, start_date, end_date)
        else:
            # Individual performance
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
    
    def _find_user_by_email_or_name(self, target: str):
        """
        Find user by exact email or partial name match (case-insensitive)
        
        Args:
            target: Email or name to search for
        
        Returns:
            Tuple of (email, user_info) or (None, None) if not found
        """
        target_lower = target.lower()
        
        # First try exact email match
        if target_lower in self.user_data:
            return target_lower, self.user_data[target_lower]
        
        # Then try partial name match
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
    
    def _get_performance_batch(self, emails: list, start_date: str, end_date: str):
        """
        Get performance metrics for multiple users across date range
        
        ✅ FIXED: Client-side filtering with proper email extraction + actual date tracking
        
        Args:
            emails: List of email addresses (lowercase)
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
        
        Returns:
            Dictionary with performance data by email
        """
        # Get all records for date range from API
        records = self.tracker.client.get_performance_records(start_date, end_date)
        
        # Normalize emails list to lowercase for matching
        emails_lower = [e.lower() for e in emails]
        
        perf_by_email = {}
        for email in emails_lower:
            perf_by_email[email] = {
                "revenue": 0, 
                "spend": 0, 
                "profit": 0, 
                "days_with_data": 0,
                "min_date": None,
                "max_date": None
            }
        
        print(f"DEBUG: Looking for {len(emails_lower)} users in {len(records)} records")
        print(f"DEBUG: Users to match: {emails_lower}")
        
        matched_count = 0
        
        # ✅ Using campaign_manager field with proper email extraction
        for record in records:
            fields = record.get("fields", {})
            campaign_manager_field = fields.get("campaign_manager", "")
            
            # Extract email using the client's helper method
            manager_email = self.tracker.client._extract_email_from_field(campaign_manager_field)
            
            # ✅ CRITICAL FIX: Normalize to lowercase for matching
            manager_email_lower = manager_email.lower() if manager_email else ""
            
            # Skip records with no valid campaign_manager
            if not manager_email_lower:
                continue
            
            # Find if this email is in our list
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
                    
                    # ✅ NEW: Track actual min/max dates from records
                    date_field = fields.get("date") or fields.get("Date") or fields.get("created_at")
                    record_date = self.tracker.client._extract_date_string(date_field)
                    
                    if record_date:
                        md = perf_by_email[manager_email_lower]["min_date"]
                        xd = perf_by_email[manager_email_lower]["max_date"]
                        if md is None or record_date < md:
                            perf_by_email[manager_email_lower]["min_date"] = record_date
                        if xd is None or record_date > xd:
                            perf_by_email[manager_email_lower]["max_date"] = record_date
                    
                except (ValueError, TypeError):
                    continue
        
        print(f"DEBUG: Matched {matched_count} records for {len([e for e in perf_by_email.values() if e['days_with_data'] > 0])} users")
        return perf_by_email
    
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
            # Find user
            email, user_info = self._find_user_by_email_or_name(name)
            if not email:
                return f"❌ User '{name}' not found in system"
            
            # Check if they're a media buyer
            if "media_buying" not in user_info.get("department", "").lower():
                return f"❌ No performance data for {user_info['name']} (not a media buyer)"
            
            # Get performance data for this individual
            perf = self._get_performance_batch([email], start_date, end_date)
            
            # Normalize email for lookup
            email_lower = email.lower()
            
            if email_lower not in perf or perf[email_lower]["days_with_data"] == 0:
                return f"❌ No data found for '{name}' between {start_date} and {end_date}"
            
            # Format response
            metrics = perf[email_lower]
            total_revenue = metrics["revenue"]
            total_spend = metrics["spend"]
            total_profit = metrics["profit"]
            roi = (total_profit / total_spend * 100) if total_spend > 0 else 0
            
            status = "✅" if roi >= 20 else "⚠️" if roi >= 10 else "❌"
            
            # Include team name in response
            team_name = self.team_mapping.get(email_lower, "Unknown Team")
            
            # ✅ NEW: Use actual data dates instead of requested range
            actual_start = metrics.get("min_date") or start_date
            actual_end = metrics.get("max_date") or end_date
            
            return (
                f"{status} **{user_info['name']}** ({team_name}) - Performance ({actual_start} to {actual_end})\n"
                f"Revenue: ${total_revenue:,.0f}\n"
                f"Spend: ${total_spend:,.0f}\n"
                f"Profit: ${total_profit:,.0f}\n"
                f"ROI: {roi:.1f}%\n"
                f"Days: {metrics['days_with_data']}"
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
            # Get all media buyers
            media_buyers = self._get_media_buyers_by_department()
            
            if not media_buyers:
                return "❌ No media buyers found"
            
            emails = [email for email, _ in media_buyers]
            perf = self._get_performance_batch(emails, start_date, end_date)
            
            if team_name:
                # ✅ FIXED: Specific leader's team - resolve person → team
                print(f"DEBUG: Fetching specific team '{team_name}' performance")
                
                # 1) Resolve leader by name/email
                leader_email, leader_info = self._find_user_by_email_or_name(team_name)
                if not leader_email:
                    return f"❌ Team leader '{team_name}' not found"
                
                leader_email_lower = leader_email.lower()
                
                # 2) Get the actual team name from mapping using leader's email
                resolved_team_name = self.team_mapping.get(leader_email_lower)
                if not resolved_team_name:
                    return f"❌ Team for '{team_name}' not configured"
                
                print(f"DEBUG: Resolved leader '{team_name}' -> {leader_email_lower}, team '{resolved_team_name}'")
                
                # 3) Collect all emails in this resolved team
                team_emails = [
                    email for email, t in self.team_mapping.items()
                    if t == resolved_team_name
                ]
                
                if not team_emails:
                    return f"❌ No members configured for {resolved_team_name}"
                
                team_revenue = 0
                team_spend = 0
                team_profit = 0
                team_members_with_data = 0
                
                # ✅ NEW: Track actual team min/max dates
                team_min_date = None
                team_max_date = None
                
                for email in team_emails:
                    email_lower = email.lower()
                    if email_lower in perf and perf[email_lower]["days_with_data"] > 0:
                        team_revenue += perf[email_lower]["revenue"]
                        team_spend += perf[email_lower]["spend"]
                        team_profit += perf[email_lower]["profit"]
                        team_members_with_data += 1
                        
                        # Track min/max dates across team members
                        md = perf[email_lower].get("min_date")
                        xd = perf[email_lower].get("max_date")
                        if md and (team_min_date is None or md < team_min_date):
                            team_min_date = md
                        if xd and (team_max_date is None or xd > team_max_date):
                            team_max_date = xd
                
                if team_members_with_data == 0:
                    return f"❌ No data found for {resolved_team_name} between {start_date} and {end_date}"
                
                roi = (team_profit / team_spend * 100) if team_spend > 0 else 0
                status = "✅" if team_profit >= 0 else "❌"
                
                # ✅ NEW: Use actual team data dates
                actual_start = team_min_date or start_date
                actual_end = team_max_date or end_date
                
                return (
                    f"{status} **{resolved_team_name}** - Performance ({actual_start} to {actual_end})\n"
                    f"Revenue: ${team_revenue:,.0f}\n"
                    f"Spend: ${team_spend:,.0f}\n"
                    f"Profit: ${team_profit:,.0f}\n"
                    f"ROI: {roi:.1f}%\n"
                    f"Members with data: {team_members_with_data}"
                )
            
            else:
                # Get performance for all teams
                print(f"DEBUG: Fetching all teams performance")
                
                # ✅ Organize by team
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
                    return f"❌ No team data found between {start_date} and {end_date}"
                
                response = f"�� **Team Performance Summary** ({start_date} to {end_date})\n\n"
                
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
            "  • `month` (last month)\n\n"
            "⏰ All times in **Montreal EST**"
        )

