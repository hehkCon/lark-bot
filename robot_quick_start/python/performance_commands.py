from datetime import datetime, timedelta
from lark_base_client import PerformanceTracker


class PerformanceCommands:
    def __init__(self, performance_tracker, user_data):
        """
        Initialize performance commands handler
        
        Args:
            performance_tracker: PerformanceTracker instance
            user_data: Dict of user email -> user info
        """
        self.performance_tracker = performance_tracker
        self.user_data = user_data
        self._latest_date_cache = None  # Cache latest date
        self._perf_cache = {}  # Cache all performance records by date range
    
    def get_team_mapping(self):
        """
        Return team structure mapping 
        """
        return {
            "Amanda's Team": ["amanda.g@intentt.com", "jonas.f@intentt.com", "brent.l@intentt.com"],
            "Dioulde's Team": ["dioulde.n@intentt.com", "rachel.l@intentt.com"],
            "Kath's Team": ["kath.g@intentt.com", "angelika.m@intentt.com", "job.c@intentt.com"],
            "Jello's Team": ["jello.c@intentt.com"]
        }
    
    def _get_latest_available_date_cached(self):
        """
        ✅ CACHED: Query Lark Base ONCE to find the latest available date
        """
        if self._latest_date_cache:
            print(f"DEBUG: Using cached latest date: {self._latest_date_cache}")
            return self._latest_date_cache
        
        print("DEBUG: Finding latest available data date (first time)...")
        
        # Try yesterday first (most common case)
        for days_back in range(1, 31):
            check_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
            records = self.performance_tracker.client.get_performance_records(check_date, check_date)
            
            if len(records) > 0:
                print(f"DEBUG: Latest available date found: {check_date}")
                self._latest_date_cache = check_date
                return check_date
        
        # Fallback to hardcoded if nothing found
        print("DEBUG: No data found in last 30 days, using fallback date")
        fallback = "2025-12-02"
        self._latest_date_cache = fallback
        return fallback
    
    def _get_performance_batch(self, start_date, end_date):
        """
        ✅ CACHED: Fetch ALL performance records for a date range ONCE
        Returns dict: {date: {email: performance_data}}
        """
        cache_key = f"{start_date}_{end_date}"
        
        if cache_key in self._perf_cache:
            print(f"DEBUG: Using cached performance data for {start_date} to {end_date}")
            return self._perf_cache[cache_key]
        
        print(f"DEBUG: Fetching all performance data for {start_date} to {end_date} (single API call)")
        
        # ✅ SINGLE API CALL - fetch entire range at once
        all_records = self.performance_tracker.client.get_performance_records(start_date, end_date)
        
        # ✅ Build lookup: {date: {email: {revenue, profit, roi, ...}}}
        perf_by_date = {}
        
        for record in all_records:
            fields = record.get("fields", {})
            
            # Extract date
            date_field = fields.get("date")
            if not date_field:
                continue
            
            if isinstance(date_field, list) and len(date_field) > 0:
                record_date = date_field[0].get("text", "") if isinstance(date_field[0], dict) else str(date_field[0])
            else:
                record_date = str(date_field)
            
            record_date_str = record_date[:10]  # YYYY-MM-DD
            
            # Extract email
            email_field = fields.get("campaign_manager", [{}])
            email = ""
            if isinstance(email_field, list) and len(email_field) > 0:
                email = email_field[0].get("text", "").lower()
            elif isinstance(email_field, str):
                email = email_field.lower()
            
            if not email or not record_date_str:
                continue
            
            # Extract metrics
            try:
                revenue = float(fields.get("revenue", 0) or 0)
                spend = float(fields.get("spend", 0) or 0)
                profit = float(fields.get("profit", 0) or 0)
                roi = float(fields.get("roi", 0) or 0)
            except (ValueError, TypeError):
                continue
            
            # Group by date and email
            if record_date_str not in perf_by_date:
                perf_by_date[record_date_str] = {}
            
            if email not in perf_by_date[record_date_str]:
                perf_by_date[record_date_str][email] = {
                    "revenue": 0,
                    "spend": 0,
                    "profit": 0,
                    "roi_total": 0,
                    "roi_count": 0
                }
            
            # Accumulate (in case multiple records per user per day - Ginsu + Bing)
            perf_by_date[record_date_str][email]["revenue"] += revenue
            perf_by_date[record_date_str][email]["spend"] += spend
            perf_by_date[record_date_str][email]["profit"] += profit
            perf_by_date[record_date_str][email]["roi_total"] += roi
            perf_by_date[record_date_str][email]["roi_count"] += 1
        
        # Cache it
        self._perf_cache[cache_key] = perf_by_date
        print(f"DEBUG: Cached {len(perf_by_date)} days of performance data")
        return perf_by_date
    
    def _get_user_performance_from_cache(self, email, target_dates, perf_data):
        """
        Get user performance from already-fetched cached data
        NO additional API calls
        """
        revenue_total = 0
        profit_total = 0
        roi_total = 0
        days_with_data = 0
        
        for target_date in target_dates:
            if target_date in perf_data and email in perf_data[target_date]:
                user_perf = perf_data[target_date][email]
                revenue_total += user_perf.get("revenue", 0)
                profit_total += user_perf.get("profit", 0)
                
                # Handle ROI properly
                if user_perf.get("roi_count", 0) > 0:
                    roi_total += user_perf.get("roi_total", 0) / user_perf.get("roi_count", 1)
                
                days_with_data += 1
        
        return {
            "revenue": revenue_total,
            "profit": profit_total,
            "roi": roi_total / days_with_data if days_with_data > 0 else 0,
            "days_with_data": days_with_data
        }
    
    def handle_performance_command(self, text, user_email):
        """
        Handle performance-related commands with date range support
        """
        
        if not text.lower().startswith("perf"):
            return None
        
        # Parse command
        parts = text.lower().split()
        if len(parts) < 2:
            return self._get_help_text()
        
        # Extract date range and target
        # ✅ CACHED: Get latest available date
        latest_date_str = self._get_latest_available_date_cached()
        latest_date = datetime.strptime(latest_date_str, "%Y-%m-%d")
        
        # ✅ DEFAULT: Last 7 days from latest available data
        target_dates = [(latest_date - timedelta(days=j)).strftime("%Y-%m-%d") for j in range(7)]
        target_dates.reverse()
        target = None
        skip_indices = set()
        
        # First pass: identify date ranges
        for i, part in enumerate(parts[1:], 1):
            if part == "yesterday":
                target_dates = [(datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")]
                skip_indices.add(i)
            elif part == "today":
                target_dates = [datetime.now().strftime("%Y-%m-%d")]
                skip_indices.add(i)
            elif part == "last" and i + 1 < len(parts) and (parts[i + 1] == "7" or parts[i + 1] == "7 days"):
                target_dates = [(latest_date - timedelta(days=j)).strftime("%Y-%m-%d") for j in range(7)]
                target_dates.reverse()
                skip_indices.add(i)
                skip_indices.add(i + 1)
                if i + 2 < len(parts) and parts[i + 2] == "days":
                    skip_indices.add(i + 2)
            elif part == "mtd" or part == "month":
                latest_month = latest_date.month
                latest_year = latest_date.year
                first_of_month = datetime(latest_year, latest_month, 1)
                
                target_dates = [
                    (first_of_month + timedelta(days=j)).strftime("%Y-%m-%d") 
                    for j in range((latest_date - first_of_month).days + 1)
                ]
                skip_indices.add(i)
            elif part == "november" or part == "nov":
                target_dates = [
                    (datetime(2025, 11, 1) + timedelta(days=j)).strftime("%Y-%m-%d") 
                    for j in range(30)
                ]
                skip_indices.add(i)
        
        # Second pass: get target (skip date-related indices)
        for i, part in enumerate(parts[1:], 1):
            if i not in skip_indices:
                target = part
                break
        
        # ✅ FETCH ONCE - Get all performance data for this date range
        perf_data = self._get_performance_batch(target_dates[0], target_dates[-1])
        
        # Route to appropriate handler
        if target == "team":
            return self._get_all_teams_performance(target_dates, perf_data)
        elif target == "me":
            return self._get_user_performance(user_email, target_dates, perf_data)
        elif target and target in ["amanda's", "dioulde's", "kath's", "jello's"]:
            team_name = f"{target.title()} team"
            return self._get_single_team_performance(team_name, target_dates, perf_data)
        elif target and target in ["amanda", "dioulde", "kath", "jello"]:
            team_map = {
                "amanda": "Amanda's Team",
                "dioulde": "Dioulde's Team",
                "kath": "Kath's Team",
                "jello": "Jello's Team"
            }
            team_name = team_map.get(target.lower())
            if team_name:
                return self._get_single_team_performance(team_name, target_dates, perf_data)
        elif target and "@" in target:
            return self._get_user_performance(target, target_dates, perf_data)
        elif target:
            team_mapping = self.get_team_mapping()
            for team_name in team_mapping.keys():
                if target.lower() in team_name.lower():
                    return self._get_single_team_performance(team_name, target_dates, perf_data)
            return f"❌ Unknown command: '{target}'. Type 'perf help' for available commands."
        else:
            return self._get_help_text()


    def _get_all_teams_performance(self, target_dates, perf_data):
        """Get performance grouped by team for date range"""
        
        if len(target_dates) == 1:
            date_label = target_dates[0]
        else:
            date_label = f"{target_dates[0]} to {target_dates[-1]}"
        
        team_mapping = self.get_team_mapping()
        
        message = f"""📊 **Team Performance - {date_label}**\n\n"""
        
        total_revenue = 0
        total_profit = 0
        total_count = 0
        
        for team_name, team_emails in team_mapping.items():
            team_revenue = 0
            team_profit = 0
            team_count = 0
            
            for email in team_emails:
                user_perf = self._get_user_performance_from_cache(email, target_dates, perf_data)
                revenue_total = user_perf["revenue"]
                profit_total = user_perf["profit"]
                
                if revenue_total > 0 or profit_total > 0:
                    team_revenue += revenue_total
                    team_profit += profit_total
                    team_count += 1
                    total_revenue += revenue_total
                    total_profit += profit_total
            
            if team_count > 0:
                user_targets = self.performance_tracker.get_daily_user_target(target_dates[0], num_media_buyers=9)
                daily_profit_target = user_targets.get("profit_target", 0) if user_targets else 0
                
                profit_target = daily_profit_target * team_count * len(target_dates)
                profit_pct = (team_profit / profit_target * 100) if profit_target > 0 else 0
                
                status = "✅" if profit_pct >= 100 else "⚠️" if profit_pct >= 80 else "❌"
                
                message += f"{status} **{team_name}** ({team_count} people): ${team_revenue:,.0f} rev / ${team_profit:,.0f} profit ({profit_pct:.0f}% of target)\n"
        
        if total_count > 0:
            message += f"\n💰 **All Teams Total:**\n"
            message += f"• Total Revenue: ${total_revenue:,.0f}\n"
            message += f"• Total Profit: ${total_profit:,.0f}\n"
            message += f"• Total Members: {total_count}\n"
            message += f"• Period: {len(target_dates)} day(s)"
        else:
            message = f"❌ No performance data for the selected period"
        
        return message


    def _get_single_team_performance(self, team_name, target_dates, perf_data):
        """Get performance for a specific team with individual member breakdown"""
        
        if len(target_dates) == 1:
            date_label = target_dates[0]
        else:
            date_label = f"{target_dates[0]} to {target_dates[-1]}"
        
        team_mapping = self.get_team_mapping()
        
        if team_name not in team_mapping:
            return f"❌ Team '{team_name}' not found"
        
        team_emails = team_mapping[team_name]
        
        message = f"""📊 **{team_name} - {date_label}**\n\n"""
        
        team_revenue = 0
        team_profit = 0
        team_count = 0
        
        for email in team_emails:
            user_info = self.user_data.get(email)
            if not user_info:
                continue
            
            user_name = user_info.get("name", "")
            user_perf = self._get_user_performance_from_cache(email, target_dates, perf_data)
            
            revenue_total = user_perf["revenue"]
            profit_total = user_perf["profit"]
            avg_roi = user_perf["roi"]
            days_with_data = user_perf["days_with_data"]
            
            if days_with_data > 0:
                team_revenue += revenue_total
                team_profit += profit_total
                team_count += 1
                
                user_targets = self.performance_tracker.get_daily_user_target(target_dates[0], num_media_buyers=9)
                daily_profit_target = user_targets.get("profit_target", 0) if user_targets else 0
                
                profit_target = daily_profit_target * len(target_dates)
                profit_pct = (profit_total / profit_target * 100) if profit_target > 0 else 0
                
                status = "✅" if profit_pct >= 100 else "⚠️" if profit_pct >= 80 else "❌"
                
                message += f"{status} {user_name}: ${revenue_total:,.0f} rev / ${profit_total:,.0f} profit ({profit_pct:.0f}%) | Avg ROI: {avg_roi:.1f}%\n"
            else:
                message += f"❌ {user_name}: No data\n"
        
        if team_count > 0:
            user_targets = self.performance_tracker.get_daily_user_target(target_dates[0], num_media_buyers=9)
            daily_profit_target = user_targets.get("profit_target", 0) if user_targets else 0
            team_target = daily_profit_target * team_count * len(target_dates)
            team_profit_pct = (team_profit / team_target * 100) if team_target > 0 else 0
            
            message += f"\n💰 **{team_name} Total:**\n"
            message += f"• Revenue: ${team_revenue:,.0f}\n"
            message += f"• Profit: ${team_profit:,.0f} ({team_profit_pct:.0f}% of target)\n"
            message += f"• Members: {team_count}\n"
            message += f"• Period: {len(target_dates)} day(s)"
        
        return message


    def _get_user_performance(self, email, target_dates, perf_data):
        """Get performance for a specific user across date range"""
        
        if len(target_dates) == 1:
            date_label = target_dates[0]
        else:
            date_label = f"{target_dates[0]} to {target_dates[-1]}"
        
        # Find user in user_data
        user_info = None
        lookup_email = email
        
        if email in self.user_data:
            user_info = self.user_data[email]
        else:
            for e, info in self.user_data.items():
                if email.lower() in e.lower() or e.lower() in email.lower():
                    user_info = info
                    lookup_email = e
                    break
        
        if not user_info:
            return f"❌ User '{email}' not found in system"
        
        user_name = user_info.get("name", "")
        user_perf = self._get_user_performance_from_cache(lookup_email, target_dates, perf_data)
        
        revenue_total = user_perf["revenue"]
        profit_total = user_perf["profit"]
        avg_roi = user_perf["roi"]
        days_with_data = user_perf["days_with_data"]
        
        if days_with_data == 0:
            return f"❌ No performance data for {user_name} in selected period"
        
        user_targets = self.performance_tracker.get_daily_user_target(target_dates[0], num_media_buyers=9)
        daily_revenue_target = user_targets.get("revenue_target", 0) if user_targets else 0
        daily_profit_target = user_targets.get("profit_target", 0) if user_targets else 0
        
        revenue_target = daily_revenue_target * len(target_dates)
        profit_target = daily_profit_target * len(target_dates)
        
        revenue_pct = (revenue_total / revenue_target * 100) if revenue_target > 0 else 0
        profit_pct = (profit_total / profit_target * 100) if profit_target > 0 else 0
        
        message = f"""📊 **{user_name}'s Performance - {date_label}**


• Revenue: ${revenue_total:,.0f} / ${revenue_target:,.0f} ({revenue_pct:.0f}%)
• Profit: ${profit_total:,.0f} / ${profit_target:,.0f} ({profit_pct:.0f}% of target)
• Avg ROI: {avg_roi:.1f}%
• Days with data: {days_with_data}"""
        
        return message


    def _get_help_text(self):
        """Return help text for performance commands"""
        return """�� **Performance Command Help**

⏰ **Default: Last 7 Days** (automatically uses latest available data)

**View Your Performance:**
• `perf me` - Last 7 days
• `perf me yesterday` - Yesterday only
• `perf me last 7` - Last 7 days
• `perf me mtd` - Month to date (1st to today)


**View All Teams:**
• `perf team` - Last 7 days
• `perf team yesterday` - Yesterday only
• `perf team last 7` - Last 7 days
• `perf team mtd` - Month to date


**View Specific Team (with individual breakdown):**
• `perf amanda` - Amanda's Team last 7 days
• `perf amanda yesterday` - Yesterday only
• `perf amanda last 7` - Last 7 days
• `perf amanda mtd` - Month to date
• `perf amanda november` - Full November
• `perf dioulde`, `perf kath`, `perf jello` - Other teams


**Manager - View Specific Person:**
• `perf amanda.g@intentt.com` - Last 7 days
• `perf amanda.g@intentt.com yesterday` - Yesterday
• `perf amanda.g@intentt.com last 7` - Last 7 days
• `perf amanda.g@intentt.com mtd` - Month to date
• `perf amanda.g@intentt.com november` - Full November


**Examples:**
perf me
perf me mtd
perf team last 7
perf amanda mtd
perf amanda.g@intentt.com last 7"""
