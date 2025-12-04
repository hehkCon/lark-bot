# performance_commands.py - FINAL CORRECTED VERSION
# Fixed: Use proper date ranges instead of just "today"

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
        
        Args:
            emails: List of email addresses
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
        
        Returns:
            Dictionary with performance data by email
        """
        records = self.tracker.client.get_performance_records(start_date, end_date)
        
        perf_by_email = {}
        for email in emails:
            perf_by_email[email] = {"revenue": 0, "spend": 0, "profit": 0, "days_with_data": 0}
        
        # ✅ Using campaign_manager field with proper email extraction
        for record in records:
            fields = record.get("fields", {})
            campaign_manager_field = fields.get("campaign_manager", "")
            
            # Extract email using the client's helper method
            manager_email = self.tracker.client._extract_email_from_field(campaign_manager_field)
            
            # Skip records with no valid campaign_manager
            if not manager_email:
                continue
            
            # Find if this email is in our list
            if manager_email in emails:
                try:
                    revenue = float(fields.get("revenue", 0) or 0)
                    spend = float(fields.get("spend", 0) or 0)
                    profit = float(fields.get("profit", 0) or 0)
                    
                    perf_by_email[manager_email]["revenue"] += revenue
                    perf_by_email[manager_email]["spend"] += spend
                    perf_by_email[manager_email]["profit"] += profit
                    perf_by_email[manager_email]["days_with_data"] += 1
                except (ValueError, TypeError):
                    continue
        
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
• `perf amanda` - Amanda's team
• `perf amanda yesterday` - Team yesterday

**Date Range Options:**
• `yesterday` - Previous day
• `last 7 days` - Previous 7 days (default)
• `last 14 days` - Previous 14 days
• `last 30 days` - Previous 30 days
• `mtd` - Month-to-date
• `today` - Today only

Type `perf help` anytime for this menu! 🚀"""
    
    
    def handle_performance_command(self, text: str, user_open_id: str):
        """
        Main handler for performance commands
        
        Args:
            text: Command text (e.g., "perf jonas last 7 days")
            user_open_id: Lark user ID who sent command
        
        Returns:
            Response message
        """
        from datetime import datetime, timedelta
        
        # Parse command
        parts = text.lower().strip().split()
        if not parts or parts[0] != "perf":
            return "❌ Invalid command"
        
        # Get command parts
        if len(parts) == 1:
            # Just "perf"
            return "❌ Use: perf me, perf team, perf [name], etc. Type 'perf help' for options."
        
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
        
        # Calculate date range
        today = datetime.now().strftime("%Y-%m-%d")
        if "yesterday" in date_range:
            yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            start_date, end_date = yesterday, yesterday
        elif "mtd" in date_range:
            month_start = datetime.now().replace(day=1).strftime("%Y-%m-%d")
            start_date, end_date = month_start, today
        elif "last 30" in date_range:
            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
            end_date = today
        elif "last 14" in date_range:
            start_date = (datetime.now() - timedelta(days=14)).strftime("%Y-%m-%d")
            end_date = today
        elif "today" in date_range:
            start_date, end_date = today, today
        else:  # Default: last 7 days
            start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
            end_date = today
        
        print(f"DEBUG: Fetching performance data for {start_date} to {end_date}")
        
        # Handle different command types
        if not search_target or search_target == "help":
            return self._get_help_text()
        elif search_target == "me":
            return "❌ Can't determine your email. Contact admin to register."
        elif search_target == "team":
            # Show all team performance
            return self._get_team_performance(start_date, end_date)
        else:
            # Find user and get performance
            email, user_info = self._find_user_by_email_or_name(search_target)
            if not email:
                return f"❌ User '{search_target}' not found in system"
            
            # Check if they're a media buyer
            if "media_buying" in user_info.get("department", ""):
                # ✅ FIXED: Use date range instead of just today
                perf = self._get_performance_batch([email], start_date, end_date)
                
                if email in perf and (perf[email]["revenue"] > 0 or perf[email]["spend"] > 0 or perf[email]["profit"] > 0):
                    # Calculate metrics from batch result
                    metrics = perf[email]
                    total_revenue = metrics["revenue"]
                    total_spend = metrics["spend"]
                    total_profit = metrics["profit"]
                    roi = (total_profit / total_spend * 100) if total_spend > 0 else 0
                    
                    status = "✅" if roi >= 20 else "⚠️" if roi >= 10 else "❌"
                    
                    message = f"""{status} **{user_info["name"]}'s Performance** ({start_date} to {end_date})

Revenue: ${total_revenue:,.0f}
Spend: ${total_spend:,.0f}
Profit: ${total_profit:,.0f}
ROI: {roi:.1f}%
Days: {metrics["days_with_data"]}"""
                    
                    return message
                else:
                    return f"❌ No performance data for {user_info['name']} from {start_date} to {end_date}"
            
            # Non-media-buying user
            return f"❌ No performance data for {user_info['name']} in selected period"
    
    
    def _get_team_performance(self, start_date: str, end_date: str):
        """Get all teams performance"""
        # Get all media buyers
        media_buyers = self._get_media_buyers_by_department()
        
        if not media_buyers:
            return "❌ No media buyers found"
        
        emails = [email for email, _ in media_buyers]
        perf = self._get_performance_batch(emails, start_date, end_date)
        
        total_rev = sum(p["revenue"] for p in perf.values())
        total_spend = sum(p["spend"] for p in perf.values())
        total_profit = sum(p["profit"] for p in perf.values())
        roi = (total_profit / total_spend * 100) if total_spend > 0 else 0
        
        status = "✅" if total_profit > 0 else "⚠️"
        
        return f"""{status} **Team Performance** ({start_date} to {end_date})

Revenue: ${total_rev:,.0f}
Spend: ${total_spend:,.0f}
Profit: ${total_profit:,.0f}
ROI: {roi:.1f}%"""
