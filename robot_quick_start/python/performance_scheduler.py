# ================== performance_scheduler.py (FIXED) ==================
# FIXES:
# 1. ✅ Changed timezone from "US/Eastern" to "America/Toronto" (Montreal EST)
# 2. ✅ Accepts performance_tracker parameter (uses singleton from server.py)
# 3. ✅ Passes date explicitly to get_today_performance() and get_today_projections()
# 4. ✅ Calculates date using Montreal timezone before passing to tracker


import os
import threading
import time
from datetime import datetime
import pytz
from api import MessageApiClient


class PerformanceScheduler:
    def __init__(self, message_api_client, performance_tracker, team_chat_mapping, timezone="America/Toronto"):
        """
        ✅ FIXED: Initialize the performance scheduler with Montreal timezone
        
        Args:
            message_api_client: MessageApiClient instance for sending messages
            performance_tracker: PerformanceTracker instance for fetching data
            team_chat_mapping: Dict mapping team names to chat IDs
            timezone: Timezone for scheduling (default: America/Toronto for Montreal EST)
        """
        self.message_api_client = message_api_client
        self.performance_tracker = performance_tracker
        self.team_chat_mapping = team_chat_mapping
        self.timezone = pytz.timezone(timezone)
        self.running = False
        self.scheduler_thread = None
        self.last_sent_date = None
        
        print(f"DEBUG: PerformanceScheduler initialized with timezone: {timezone}")
    
    def start(self):
        """Start the scheduler in a background thread"""
        if self.running:
            print("DEBUG: Scheduler already running")
            return
        
        self.running = True
        self.scheduler_thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self.scheduler_thread.start()
        print("DEBUG: Performance scheduler started")
    
    def stop(self):
        """Stop the scheduler"""
        self.running = False
        print("DEBUG: Performance scheduler stopped")
    
    def _run_scheduler(self):
        """Main scheduler loop - runs in background thread"""
        print("DEBUG: Scheduler loop started")
        
        while self.running:
            try:
                now = datetime.now(self.timezone)
                today = now.date()
                
                # 9:00 AM - 9:15 AM: Check every 3 minutes for 9:10 AM
                if now.hour == 9 and 0 <= now.minute <= 15:
                    if now.minute == 10 and self.last_sent_date != today:
                        print("DEBUG: Time is 9:10 AM EST (Montreal) - sending performance updates")
                        self._send_all_team_updates(today)
                        self.last_sent_date = today
                        
                        # Wait 65 seconds to avoid duplicate sends in the same minute
                        time.sleep(65)
                    else:
                        # During 9:00-9:15 AM window, check every 3 minutes
                        print(f"DEBUG: In 9:00-9:15 AM window, checking in 3 minutes (current time: {now.strftime('%H:%M:%S')})")
                        time.sleep(180)
                else:
                    # Rest of day: check every 2 hours (7200 seconds)
                    print(f"DEBUG: Outside 9:00-9:15 AM window, checking in 2 hours (current time: {now.strftime('%H:%M:%S')})")
                    time.sleep(7200)
            
            except Exception as e:
                print(f"ERROR: Scheduler error: {e}")
                time.sleep(7200)
    
    def _send_all_team_updates(self, date=None):
        """
        ✅ FIXED: Fetch performance data and send to all teams
        
        Args:
            date: Date to fetch performance for (optional, defaults to today in Montreal)
        """
        try:
            # ✅ FIXED: Calculate date in Montreal timezone
            if not date:
                now = datetime.now(self.timezone)
                date = now.date()
            
            date_str = date.isoformat()  # Convert to "YYYY-MM-DD" format
            
            print(f"DEBUG: Fetching performance data from Lark Base for {date_str}")
            
            # ✅ FIXED: Pass date explicitly to tracker methods
            performance_data = self.performance_tracker.get_today_performance(date_str)
            projections_data = self.performance_tracker.get_today_projections(date_str)
            
            if not performance_data:
                print("ERROR: No performance data available for today")
                return
            
            if not projections_data:
                print("ERROR: No projection data available for today")
                return
            
            # Compare performance to targets
            comparison = self.performance_tracker.compare_performance_to_targets(
                performance_data, 
                projections_data
            )
            
            # Send message to each team
            for team_name, chat_id in self.team_chat_mapping.items():
                try:
                    # Generate personalized message
                    message = self.performance_tracker.generate_performance_message(
                        team_name, 
                        comparison
                    )
                    
                    # Send to team group chat
                    print(f"DEBUG: Sending performance update to {team_name} (chat: {chat_id})")
                    self.message_api_client.send_text_with_chat_id(chat_id, message)
                    
                    print(f"DEBUG: Successfully sent message to {team_name}")
                
                except Exception as e:
                    print(f"ERROR: Failed to send message to {team_name}: {e}")
                
                # Small delay between messages to avoid rate limiting
                time.sleep(1)
        
        except Exception as e:
            print(f"ERROR: Failed to send performance updates: {e}")



def initialize_performance_scheduler(message_api_client, performance_tracker):
    """
    ✅ FIXED: Initialize and start the performance scheduler
    
    Args:
        message_api_client: MessageApiClient instance
        performance_tracker: PerformanceTracker instance (from server.py singleton)
    
    Call this from server.py during app startup
    """
    # Team to chat ID mapping
    team_chat_mapping = {
        "Dioulde's team": "oc_fdb7932f2822ba72af2097415bd9950f",
        "Kath's team": "oc_adf04e6adc2205c661e177354abad176",
        "Amanda's team": "oc_2baefe6e05e47f00b376c33e5d938101",
        "Jello's team": "oc_b017b223e054e80c14b5957bc77f8467"
    }
    
    # ✅ FIXED: Use existing performance_tracker instead of creating new one
    scheduler = PerformanceScheduler(
        message_api_client=message_api_client,
        performance_tracker=performance_tracker,
        team_chat_mapping=team_chat_mapping,
        timezone="America/Toronto"  # ✅ FIXED: Montreal EST timezone
    )
    
    # Start scheduler
    scheduler.start()
    
    print("DEBUG: Performance scheduler initialized and started")
    return scheduler
