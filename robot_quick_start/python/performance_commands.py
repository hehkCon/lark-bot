# CRITICAL FIX: Team command parsing and date tracking
# This version fixes the index offset bug in team command detection

# In handle_performance_command() method, REPLACE the entire parsing section:

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
