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
    
    def get_team_mapping(self):
        """
        Return team structure mapping
        """
        return {
            "Amanda's Team": ["amanda.g@intentt.com", "jonas.f@intentt.com", "brent.l@intentt.com"],
            "Dioulde's Team": ["dioulde.n@intentt.com", "rachel.l@intentt.com"],
            "Kath's Team": ["kath.g@intentt.com", "angelika.m@intentt.com"],
            "Jello's Team": ["jello.c@intentt.com", "job.c@intentt.com"]
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
        target_dates = [datetime.now().strftime("%Y-%m-%d")]  # Default: today
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
            elif part == "last" and i + 1 < len(parts) and parts[i + 1] == "7":
                # Last 7 days
                target_dates = [(datetime.now() - timedelta(days=j)).strftime("%Y-%m-%d") for j in range(7)]
                target_dates.reverse()
                skip_indices.add(i)
                skip_indices.add(i + 1)
            elif part == "mtd" or part == "month":
                # Month to date (1st of current month to today)
                today = datetime.now()
                first_of_month = today.replace(day=1)
                target_dates = [(first_of_month + timedelta(days=j)).strftime("%Y-%m-%d") 
                               for j in range((today - first_of_month).days + 1)]
                skip_indices.add(i)
        
        # Second pass: get target (skip date-related indices)
        for i, part in enumerate(parts[1:], 1):
            if i not in skip_indices:
                target = part
                break
        
        # Route to appropriate handler
        if target == "team":
            return self._get_all_teams_performance(target_dates)
        elif target == "me":
            return self._get_user_performance(user_email, target_dates)
        elif target and target in ["amanda's", "dioulde's", "kath's", "jello's"]:
            team_name = f"{target} team"
            return self._get_single_team_performance(team_name, target_dates)
        elif target and "@" in target:
            # Extract email from markdown link format if present
            if "[" in target and "](" in target:
                email = target.split("[")[1].split("](")[0]
            else:
                email = target
            return self._get_user_performance(email, target_dates)
        elif target:
            # Try to match team name
            team_mapping = self.get_team_mapping()
            for team_name in team_mapping.keys():
                if target.lower() in team_name.lower():
                    return self._get_single_team_performance(team_name, target_dates)
            return f"❌ Unknown command: '{target}'. Type 'perf help' for available commands."
        else:
            return self._get_help_text()


    def _get_all_teams_performance(self, target_dates):
        """Get performance grouped by team for date range"""
        
        if len(target_dates) == 1:
            date_label = target_dates[0]
        else:
            date_label = f"{target_dates[0]} to {target_dates[-1]}"
        
        team_mapping = self.get_team_mapping()
        
        message = f"""📊 **Team Performance - {date_label}**

"""
        
        total_revenue = 0
        total_profit = 0
        total_count = 0
        
        for team_name, team_emails in team_mapping.items():
            team_revenue = 0
            team_profit = 0
            team_count = 0
            
            for email in team_emails:
                revenue_total = 0
                profit_total = 0
                
                for target_date in target_dates:
                    user_performance = self.performance_tracker.get_user_performance(email, target_date)
                    if user_performance:
                        revenue_total += user_performance.get("revenue", 0)
                        profit_total += user_performance.get("profit", 0)
                
                if revenue_total > 0 or profit_total > 0:
                    team_revenue += revenue_total
                    team_profit += profit_total
                    team_count += 1
                    total_revenue += revenue_total
                    total_profit += profit_total
                    total_count += 1
            
            if team_count > 0:
                # Get daily target and multiply by number of days
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


    def _get_single_team_performance(self, team_name, target_dates):
        """Get performance for a specific team with individual member breakdown"""
        
        if len(target_dates) == 1:
            date_label = target_dates[0]
        else:
            date_label = f"{target_dates[0]} to {target_dates[-1]}"
        
        team_mapping = self.get_team_mapping()
        
        if team_name not in team_mapping:
            return f"❌ Team '{team_name}' not found"
        
        team_emails = team_mapping[team_name]
        
        message = f"""📊 **{team_name} - {date_label}**

"""
        
        team_revenue = 0
        team_profit = 0
        team_count = 0
        
        for email in team_emails:
            user_info = self.user_data.get(email)
            if not user_info:
                continue
            
            user_name = user_info.get("name", "")
            
            revenue_total = 0
            profit_total = 0
            roi_total = 0
            days_with_data = 0
            
            for target_date in target_dates:
                user_performance = self.performance_tracker.get_user_performance(email, target_date)
                
                if user_performance:
                    revenue_total += user_performance.get("revenue", 0)
                    profit_total += user_performance.get("profit", 0)
                    roi_total += user_performance.get("roi", 0)
                    days_with_data += 1
            
            if days_with_data > 0:
                team_revenue += revenue_total
                team_profit += profit_total
                team_count += 1
                
                # Get daily target
                user_targets = self.performance_tracker.get_daily_user_target(target_dates[0], num_media_buyers=9)
                daily_profit_target = user_targets.get("profit_target", 0) if user_targets else 0
                
                profit_target = daily_profit_target * len(target_dates)
                profit_pct = (profit_total / profit_target * 100) if profit_target > 0 else 0
                avg_roi = roi_total / days_with_data
                
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


    def _get_user_performance(self, email, target_dates):
        """Get performance for a specific user across date range"""
        
        # Extract email from markdown link format if present
        if "[" in email and "](" in email:
            email = email.split("[")[1].split("](")[0]
        
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
            # Try to find by partial match
            for e, info in self.user_data.items():
                if email.lower() in e.lower() or e.lower() in email.lower():
                    user_info = info
                    lookup_email = e
                    break
        
        if not user_info:
            return f"❌ User '{email}' not found in system"
        
        user_name = user_info.get("name", "")
        
        revenue_total = 0
        profit_total = 0
        roi_total = 0
        days_with_data = 0
        
        for target_date in target_dates:
            user_performance = self.performance_tracker.get_user_performance(lookup_email, target_date)
            
            if user_performance:
                revenue_total += user_performance.get("revenue", 0)
                profit_total += user_performance.get("profit", 0)
                roi_total += user_performance.get("roi", 0)
                days_with_data += 1
        
        if days_with_data == 0:
            return f"❌ No performance data for {user_name} in selected period"
        
        # Get daily target
        user_targets = self.performance_tracker.get_daily_user_target(target_dates[0], num_media_buyers=9)
        daily_revenue_target = user_targets.get("revenue_target", 0) if user_targets else 0
        daily_profit_target = user_targets.get("profit_target", 0) if user_targets else 0
        
        revenue_target = daily_revenue_target * len(target_dates)
        profit_target = daily_profit_target * len(target_dates)
        
        revenue_pct = (revenue_total / revenue_target * 100) if revenue_target > 0 else 0
        profit_pct = (profit_total / profit_target * 100) if profit_target > 0 else 0
        avg_roi = (roi_total / days_with_data) if days_with_data > 0 else 0
        
        message = f"""📊 **{user_name}'s Performance - {date_label}**


• Revenue: ${revenue_total:,.0f} / ${revenue_target:,.0f} ({revenue_pct:.0f}%)
• Profit: ${profit_total:,.0f} / ${profit_target:,.0f} ({profit_pct:.0f}% of target)
• Avg ROI: {avg_roi:.1f}%
• Days with data: {days_with_data}"""
        
        return message


    def _get_help_text(self):
        """Return help text for performance commands"""
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

