# ================== user_performance_scheduler.py (FIXED) ==================
# FIXES:
# 1. ✅ Changed timezone from "US/Eastern" to "America/Toronto" (Montreal EST)
# 2. ✅ Accepts performance_tracker parameter (uses singleton from server.py)
# 3. ✅ Passes date explicitly to get_user_performance() 
# 4. ✅ Removed hardcoded start_date logic (was problematic)
# 5. ✅ Calculates date using Montreal timezone before passing to tracker


import threading
import time
from datetime import datetime
import pytz


class UserPerformanceScheduler:
    def __init__(self, message_api_client, performance_tracker, timezone="America/Toronto"):
        """
        ✅ FIXED: Initialize user performance scheduler for individual messages
        
        Args:
            message_api_client: MessageApiClient instance
            performance_tracker: PerformanceTracker instance (from server.py singleton)
            timezone: Timezone for scheduling (default: America/Toronto for Montreal EST)
        """
        self.message_api_client = message_api_client
        self.performance_tracker = performance_tracker
        self.timezone = pytz.timezone(timezone)
        self.running = False
        self.scheduler_thread = None
        self.last_sent_date = None
        
        print(f"DEBUG: UserPerformanceScheduler initialized with timezone: {timezone}")
    
    def start(self):
        """Start the scheduler in a background thread"""
        if self.running:
            print("DEBUG: User performance scheduler already running")
            return
        
        self.running = True
        self.scheduler_thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self.scheduler_thread.start()
        print("DEBUG: User performance scheduler started")
    
    def stop(self):
        """Stop the scheduler"""
        self.running = False
        print("DEBUG: User performance scheduler stopped")
    
    def _run_scheduler(self):
        """Main scheduler loop - runs in background thread"""
        print("DEBUG: User performance scheduler loop started")
        
        while self.running:
            try:
                now = datetime.now(self.timezone)
                today = now.date()
                
                # 9:45 AM - 9:55 AM: Check every 2 minutes for 9:50 AM
                if now.hour == 9 and 45 <= now.minute <= 55:
                    if now.minute == 50 and self.last_sent_date != today:
                        print("DEBUG: Time is 9:50 AM EST (Montreal) - sending individual performance updates")
                        self._send_all_user_updates(today)
                        self.last_sent_date = today
                        
                        # Wait 65 seconds to avoid duplicate sends in the same minute
                        time.sleep(65)
                    else:
                        # During 9:45-9:55 AM window, check every 2 minutes
                        print(f"DEBUG: In 9:45-9:55 AM window, checking in 2 minutes (current time: {now.strftime('%H:%M:%S')})")
                        time.sleep(120)
                else:
                    # Rest of day: check every 2 hours
                    print(f"DEBUG: Outside 9:45-9:55 AM window, checking in 2 hours (current time: {now.strftime('%H:%M:%S')})")
                    time.sleep(7200)
            
            except Exception as e:
                print(f"ERROR: User scheduler error: {e}")
                time.sleep(7200)
    
    def _send_all_user_updates(self, date=None):
        """
        ✅ FIXED: Fetch user performance and send individual messages
        
        Args:
            date: Date to fetch performance for (optional, defaults to today in Montreal)
        """
        try:
            # ✅ FIXED: Calculate date in Montreal timezone
            if not date:
                now = datetime.now(self.timezone)
                date = now.date()
            
            date_str = date.isoformat()  # Convert to "YYYY-MM-DD" format
            
            print(f"DEBUG: Fetching individual user performance data for {date_str}")
            
            # Fetch user data from lark_user_id table
            user_data = self.performance_tracker.get_user_data()
            
            if not user_data:
                print("ERROR: No user data available")
                return
            
            # Get user targets (divided by number of media buyers)
            user_targets = self.performance_tracker.get_daily_user_target(date_str, num_media_buyers=9)
            
            if not user_targets:
                print("ERROR: No target data available")
                return
            
            # Send message to each user
            for email, user_info in user_data.items():
                try:
                    user_name = user_info.get("name", "Team Member")
                    user_key = user_info.get("lark_user_key", "")
                    
                    # ✅ FIXED: Pass date explicitly to get_user_performance()
                    user_performance = self.performance_tracker.get_user_performance(email, date_str)
                    
                    if not user_performance:
                        print(f"DEBUG: No performance data for {user_name} ({email})")
                        continue
                    
                    # Generate personalized message
                    message = self.performance_tracker.generate_user_performance_message(
                        user_name,
                        user_performance,
                        user_targets
                    )
                    
                    if not message:
                        continue
                    
                    # Send to user's 1-on-1 chat
                    print(f"DEBUG: Sending individual update to {user_name} (lark_user_key: {user_key})")
                    self.message_api_client.send_text_with_open_id(user_key, message)
                    
                    print(f"DEBUG: Successfully sent message to {user_name}")
                
                except Exception as e:
                    print(f"ERROR: Failed to send message to {user_name} ({email}): {e}")
                
                # Small delay between messages to avoid rate limiting
                time.sleep(1)
        
        except Exception as e:
            print(f"ERROR: Failed to send user performance updates: {e}")



def initialize_user_performance_scheduler(message_api_client, performance_tracker):
    """
    ✅ FIXED: Initialize and start the user performance scheduler
    
    Args:
        message_api_client: MessageApiClient instance
        performance_tracker: PerformanceTracker instance (from server.py singleton)
    """
    # ✅ FIXED: Use existing performance_tracker instead of creating new one
    scheduler = UserPerformanceScheduler(
        message_api_client=message_api_client,
        performance_tracker=performance_tracker,
        timezone="America/Toronto"  # ✅ FIXED: Montreal EST timezone
    )
    
    # Start scheduler
    scheduler.start()
    
    print("DEBUG: User performance scheduler initialized and started")
    return scheduler
