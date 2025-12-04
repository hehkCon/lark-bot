# performance_commands.py - ENHANCED with team commands and actual date tracking
# Now supports "perf team [name]" and shows actual date range from data

class PerformanceCommands:
    def __init__(self, performance_tracker, user_data: dict):
        """
        Initialize performance commands handler
        
        Args:
            performance_tracker: PerformanceTracker instance
            user_data: Dictionary of users keyed by email
        """
        self.tracker = performance_tracker
        self.user_data = user_data
        
        # Team mapping from Lark Base formula
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
        
        # Reverse mapping: team name -> list of email addresses
        self.teams_by_name = {}
        for email, team_name in self.team_mapping.items():
            if team_name not in self.teams_by_name:
                self.teams_by_name[team_name] = []
            self.teams_by_name[team_name].append(email)
    
    
    def _get_montreal_dates(self, date_range: str):
        """
        Calculate date range in Montreal EST timezone
        
        Args:
            date_range: Date range string (e.g., "last 7 days", "today", "yesterday")
        
        Returns:
            Tuple of (start_date, end_date) in YYYY-MM-DD format
        """
        from datetime import datetime, timedelta, timezone
        
        # Montreal EST timezone offset (UTC-5)
        EST_OFFSET = timezone(timedelta(hours=-5))
        now_montreal = datetime.now(EST_OFFSET)
        today_montreal = now_montreal.strftime("%Y-%m-%d")
        
        print(f"DEBUG: Montreal time now: {now_montreal.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        print(f"DEBUG: Today in Montreal: {today_montreal}")
        
        if "yesterday" in date_range:
            yesterday = (now_montreal - timedelta(days=1)).strftime("%Y-%m-%d")
            return yesterday, yesterday
        elif "mtd" in date_range:
            month_start = now_montreal.replace(day=1).strftime("%Y-%m-%d")
            return month_start, today_montreal
        elif "last 30" in date_range:
            start = (now_montreal - timedelta(days=30)).strftime("%Y-%m-%d")
            return start, today_montreal
        elif "last 14" in date_range:
            start = (now_montreal - timedelta(days=14)).strftime("%Y-%m-%d")
            return start, today_montreal
        elif "today" in date_range:
            return today_montreal, today_montreal
        else:  # Default: last 7 days
            start = (now_montreal - timedelta(days=7)).strftime("%Y-%m-%d")
            return start, today_montreal
    
    
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
        
        ✅ ENHANCED: Now returns actual date range from data
        
        Args:
            emails: List of email addresses (lowercase)
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
        
        Returns:
            Dictionary with performance data by email
            Format: {
                "email@example.com": {
                    "revenue": 0,
                    "spend": 0,
                    "profit": 0,
                    "days_with_data": 0,
                    "min_date": "2025-11-28",  # ✅ NEW
                    "max_date": "2025-12-03"   # ✅ NEW
                }
            }
        """
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
                "min_date": None,  # ✅ Track actual date range
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
                    
                    # ✅ NEW: Extract date for min/max tracking
                    date_field = fields.get("date", "")
                    if date_field:
                        record_date = self.tracker.client._extract_date_string(date_field)
                        if record_date:
                            # Update min_date
                            if perf_by_email[manager_email_lower]["min_date"] is None or record_date < perf_by_email[manager_email_lower]["min_date"]:
                                perf_by_email[manager_email_lower]["min_date"] = record_date
                            # Update max_date
                            if perf_by_email[manager_email_lower]["max_date"] is None or record_date > perf_by_email[manager_email_lower]["max_date"]:
                                perf_by_email[manager_email_lower]["max_date"] = record_date
                    
                    perf_by_email[manager_email_lower]["revenue"] += revenue
                    perf_by_email[manager_email_lower]["spend"] += spend
                    perf_by_email[manager_email_lower]["profit"] += profit
                    perf_by_email[manager_email_lower]["days_with_data"] += 1
                except (ValueError, TypeError):
                    continue
        
        print(f"DEBUG: Matched {matched_count} records for {len([e for e in perf_by_email.values() if e['days_with_data'] > 0])} users")
        return perf_by_email
    
    
    def _get_help_text(self):
        """Generate help text for perf commands"""
        return """📊 **Performance Tracker Commands**

**View Performance:**
• `perf me` - Your performance (last 7 days)
• `perf me yesterday` - Your performance yesterday
• `perf me mtd` - Your performance month-to-date

**Check Other Users:**
• `perf jonas` - Jonas's performance
• `perf jonas.f@intentt.com` - By email
• `perf amanda last 7 days` - Specific date range

**Team Performance:**
• `perf team` - All teams (last 7 days)
• `perf team amanda last 7 days` - Amanda's team
• `perf team kath yesterday` - Kath's team yesterday
• `perf team dioulde mtd` - Dioulde's team month-to-date
• `perf team jello` - Jello's team (default: last 7 days)

**Date Range Options:**
• `yesterday` - Previous day
• `last 7 days` - Previous 7 days (default)
• `last 14 days` - Previous 14 days
• `last 30 days` - Previous 30 days
• `mtd` - Month-to-date
• `today` - Today only

⏰ All times in **Montreal EST**

Type `perf help` anytime for this menu! 🚀"""
    
    
    def handle_performance_command(self, text: str, user_open_id: str):
        """
        Main handler for performance commands
        
        ✅ ENHANCED: Supports "perf team [name]" syntax
        
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
        
        # ✅ NEW: Check if this is a team command
        is_team_command = False
        if len(parts) >= 2 and parts[1] == "team":
            is_team_command = True
            parts = parts[1:]  # Remove "team" from parts, so remaining logic is the same
        
        # Parse date range (default: last 7 days)
        date_range = "last 7 days"
        search_target = None
        
        # Find where date range starts (if any)
        date_keywords = ["yesterday", "today", "last", "mtd", "month"]
        date_start_idx = None
        for i, part in enumerate(parts[1:], 1):
            if part in date_keywords:
                date_start_idx = i
                break
        
        if date_start_idx:
            search_target = " ".join(parts[1:date_start_idx]).strip()
            date_range = " ".join(parts[date_start_idx:]).strip()
        else:
            search_target = " ".join(parts[1:]).strip() if len(parts) > 1 else None
        
        # ✅ UPDATED: Use Montreal EST timezone
        start_date, end_date = self._get_montreal_dates(date_range)
        
        print(f"DEBUG: Fetching performance data for {start_date} to {end_date}")
        print(f"DEBUG: Is team command: {is_team_command}, Target: {search_target}")
        
        # Handle different command types
        if not search_target or search_target == "help":
            return self._get_help_text()
        elif search_target == "me":
            return "❌ Can't determine your email. Contact admin to register."
        elif search_target == "team" and not is_team_command:
            # Show all team performance (perf team without name)
            return self._get_team_performance(None, start_date, end_date)
        elif is_team_command:
            # ✅ NEW: Handle "perf team [name]" command
            return self._get_team_performance(search_target, start_date, end_date)
        else:
            # Show individual performance
            return self._get_individual_performance(search_target, start_date, end_date)
    
    
    def _get_individual_performance(self, search_target: str, start_date: str, end_date: str):
        """
        Get individual user performance
        
        ✅ ENHANCED: Uses actual date range from data
        """
        # Find user and get performance
        email, user_info = self._find_user_by_email_or_name(search_target)
        if not email:
            return f"❌ User '{search_target}' not found in system"
        
        # Check if they're a media buyer
        if "media_buying" in user_info.get("department", ""):
            # ✅ Use date range with proper email normalization
            perf = self._get_performance_batch([email], start_date, end_date)
            
            # Normalize email for lookup
            email_lower = email.lower()
            
            if email_lower in perf and (perf[email_lower]["revenue"] > 0 or perf[email_lower]["spend"] > 0 or perf[email_lower]["profit"] > 0):
                # Calculate metrics from batch result
                metrics = perf[email_lower]
                total_revenue = metrics["revenue"]
                total_spend = metrics["spend"]
                total_profit = metrics["profit"]
                roi = (total_profit / total_spend * 100) if total_spend > 0 else 0
                
                status = "✅" if roi >= 20 else "⚠️" if roi >= 10 else "❌"
                
                # Include team name in response
                team_name = self.team_mapping.get(email_lower, "Unknown Team")
                
                # ✅ NEW: Use actual date range from data
                actual_start = metrics["min_date"] or start_date
                actual_end = metrics["max_date"] or end_date
                date_range_display = f"{actual_start} to {actual_end}"
                
                message = f"""{status} **{user_info["name"]}** ({team_name}) - Performance ({date_range_display})

Revenue: ${total_revenue:,.0f}
Spend: ${total_spend:,.0f}
Profit: ${total_profit:,.0f}
ROI: {roi:.1f}%
Days: {metrics["days_with_data"]}"""
                
                return message
            else:
                # Better error message with troubleshooting hints
                return f"""❌ **{user_info['name']}** - No data found ({start_date} to {end_date})

**Possible reasons:**
• Data not uploaded yet for this period
• Try: `perf {user_info['name'].lower()} last 14 days` to check if data exists
• Or: `perf {user_info['name'].lower()} today` for today's data

**All times in Montreal EST**"""
        
        # Non-media-buying user
        return f"❌ No performance data for {user_info['name']} in selected period"
    
    
    def _get_team_performance(self, team_lead_name: str, start_date: str, end_date: str):
        """
        Get team performance
        
        ✅ ENHANCED: Supports specific team by team lead name (e.g., "amanda", "kath")
                      Uses actual date range from data
        
        Args:
            team_lead_name: Team lead name (e.g., "amanda") or None for all teams
            start_date: Start date
            end_date: End date
        """
        # Get all media buyers
        media_buyers = self._get_media_buyers_by_department()
        
        if not media_buyers:
            return "❌ No media buyers found"
        
        all_emails = [email for email, _ in media_buyers]
        perf = self._get_performance_batch(all_emails, start_date, end_date)
        
        # ✅ NEW: Handle specific team request
        if team_lead_name:
            # Find the team lead and get their team
            lead_email, lead_info = self._find_user_by_email_or_name(team_lead_name)
            
            if not lead_email:
                return f"❌ Team lead '{team_lead_name}' not found in system"
            
            # Get team name from mapping
            lead_email_lower = lead_email.lower()
            team_name = self.team_mapping.get(lead_email_lower)
            
            if not team_name:
                return f"❌ '{lead_info['name']}' is not a team lead"
            
            # Get team members
            team_members = self.teams_by_name.get(team_name, [])
            
            # Calculate team stats
            team_revenue = 0
            team_spend = 0
            team_profit = 0
            min_date = None
            max_date = None
            
            for email in team_members:
                if email in perf and perf[email]["days_with_data"] > 0:
                    team_revenue += perf[email]["revenue"]
                    team_spend += perf[email]["spend"]
                    team_profit += perf[email]["profit"]
                    
                    # Track actual min/max dates
                    record_min = perf[email]["min_date"]
                    record_max = perf[email]["max_date"]
                    
                    if record_min and (min_date is None or record_min < min_date):
                        min_date = record_min
                    if record_max and (max_date is None or record_max > max_date):
                        max_date = record_max
            
            # Format response
            team_roi = (team_profit / team_spend * 100) if team_spend > 0 else 0
            status = "✅" if team_profit > 0 else "⚠️"
            
            # ✅ NEW: Use actual date range
            actual_start = min_date or start_date
            actual_end = max_date or end_date
            date_range_display = f"{actual_start} to {actual_end}"
            
            return f"""{status} **{team_name}** - Performance ({date_range_display})

Revenue: ${team_revenue:,.0f}
Spend: ${team_spend:,.0f}
Profit: ${team_profit:,.0f}
ROI: {team_roi:.1f}%

⏰ All times in Montreal EST"""
        
        # ✅ Show all teams (perf team without name)
        teams_data = {
            "Amanda's Team": {"revenue": 0, "spend": 0, "profit": 0, "min_date": None, "max_date": None},
            "Kath's Team": {"revenue": 0, "spend": 0, "profit": 0, "min_date": None, "max_date": None},
            "Dioulde's Team": {"revenue": 0, "spend": 0, "profit": 0, "min_date": None, "max_date": None},
            "Jello's Team": {"revenue": 0, "spend": 0, "profit": 0, "min_date": None, "max_date": None},
        }
        
        for email, metrics in perf.items():
            team_name = self.team_mapping.get(email, "Unknown Team")
            if team_name in teams_data and metrics["days_with_data"] > 0:
                teams_data[team_name]["revenue"] += metrics["revenue"]
                teams_data[team_name]["spend"] += metrics["spend"]
                teams_data[team_name]["profit"] += metrics["profit"]
                
                # Track min/max dates
                record_min = metrics["min_date"]
                record_max = metrics["max_date"]
                
                if record_min and (teams_data[team_name]["min_date"] is None or record_min < teams_data[team_name]["min_date"]):
                    teams_data[team_name]["min_date"] = record_min
                if record_max and (teams_data[team_name]["max_date"] is None or record_max > teams_data[team_name]["max_date"]):
                    teams_data[team_name]["max_date"] = record_max
        
        # Build response
        response = f"📊 **Team Performance Summary** ({start_date} to {end_date})\n\n"
        
        for team_name, data in teams_data.items():
            if data["spend"] > 0:  # Only show teams with data
                roi = (data["profit"] / data["spend"] * 100) if data["spend"] > 0 else 0
                status = "✅" if data["profit"] > 0 else "⚠️"
                
                # ✅ NEW: Use actual date range for each team
                team_date_start = data["min_date"] or start_date
                team_date_end = data["max_date"] or end_date
                
                response += f"{status} **{team_name}** ({team_date_start} to {team_date_end})\n"
                response += f"   Revenue: ${data['revenue']:,.0f} | Spend: ${data['spend']:,.0f} | Profit: ${data['profit']:,.0f} (ROI: {roi:.1f}%)\n\n"
        
        response += f"⏰ All times in Montreal EST"
        
        return response.strip()