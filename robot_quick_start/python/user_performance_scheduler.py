import threading
import time
from datetime import datetime
import pytz
from api import MessageApiClient
from lark_base_client import PerformanceTracker

class UserPerformanceScheduler:
    def __init__(self, message_api_client, performance_tracker, timezone="US/Eastern"):
        """
        Initialize user performance scheduler for individual messages
        """
        self.message_api_client = message_api_client
        self.performance_tracker = performance_tracker
        self.timezone = pytz.timezone(timezone)
        self.running = False
        self.scheduler_thread = None
        self.last_sent_date = None
        self.start_date = datetime(2025, 12, 3, tzinfo=self.timezone).date()
    
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
                
                # Skip if before start date
                if today < self.start_date:
                    print(f"DEBUG: Before start date ({self.start_date}), skipping user scheduler")
                    time.sleep(7200)
                    continue
                
                # 9:45 AM - 9:55 AM: Check every 2 minutes for 9:50 AM
                if now.hour == 9 and 45 <= now.minute <= 55:
                    if now.minute == 50 and self.last_sent_date != today:
                        print("DEBUG: Time is 9:50 AM EST - sending individual performance updates")
                        self._send_all_user_updates()
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
    
    def _send_all_user_updates(self):
        """Fetch user performance and send individual messages"""
        try:
            print("DEBUG: Fetching individual user performance data")
            
            # Fetch user data from lark_user_id table
            user_data = self.performance_tracker.get_user_data()
            
            if not user_data:
                print("ERROR: No user data available")
                return
            
            # Get user targets (divided by number of media buyers)
            user_targets = self.performance_tracker.get_daily_user_target(num_media_buyers=9)
            
            if not user_targets:
                print("ERROR: No projection data available")
                return
            
            # Send message to each user
            for email, user_info in user_data.items():
                try:
                    user_name = user_info.get("name", "Team Member")
                    user_key = user_info.get("lark_user_key", "")
                    
                    # Get this user's performance
                    user_performance = self.performance_tracker.get_user_performance(email)
                    
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


def initialize_user_performance_scheduler(message_api_client, token_manager, app_token, performance_table_id, lark_user_id_table_id):
    """
    Initialize and start the user performance scheduler
    """
    # Get tenant access token
    tenant_token = token_manager.get_token()
    
    # Initialize performance tracker
    performance_tracker = PerformanceTracker(
        app_token=app_token,
        performance_table_id=performance_table_id,
        projections_table_id=lark_user_id_table_id,
        tenant_access_token=tenant_token,
        host="https://open.larksuite.com"
    )
    
    # Initialize scheduler
    scheduler = UserPerformanceScheduler(
        message_api_client=message_api_client,
        performance_tracker=performance_tracker,
        timezone="US/Eastern"  # EST
    )
    
    # Start scheduler
    scheduler.start()
    
    print("DEBUG: User performance scheduler initialized and started")
    return scheduler

