from datetime import datetime, timedelta
import requests
import json

class PerformanceTracker:
    def __init__(self, app_token, performance_table_id, projections_table_id, tenant_access_token, host="https://open.larksuite.com"):
        """
        Initialize the performance tracker
        
        Args:
            app_token: App token for authentication
            performance_table_id: Table ID for performance data
            projections_table_id: Table ID for projections/targets
            tenant_access_token: Tenant access token
            host: Lark API host
        """
        self.app_token = app_token
        self.performance_table_id = performance_table_id
        self.projections_table_id = projections_table_id
        self.tenant_access_token = tenant_access_token
        self.host = host
        self.performance_client = LarkBaseClient(
            app_token=app_token,
            table_id=performance_table_id,
            tenant_access_token=tenant_access_token,
            host=host
        )
        self.projections_client = LarkBaseClient(
            app_token=app_token,
            table_id=projections_table_id,
            tenant_access_token=tenant_access_token,
            host=host
        )
    
    def get_today_performance(self):
        """Fetch today's performance data from Lark Base"""
        try:
            records = self.performance_client.list_records()
            today = datetime.now().strftime("%Y-%m-%d")
            
            performance_data = {}
            for record in records:
                fields = self.performance_client.get_record_fields(record)
                record_date = fields.get("date", "")
                
                if record_date == today:
                    team = fields.get("team", "unknown")
                    performance_data[team] = {
                        "revenue": float(fields.get("revenue", 0)) if fields.get("revenue") else 0,
                        "spend": float(fields.get("spend", 0)) if fields.get("spend") else 0,
                        "profit": float(fields.get("profit", 0)) if fields.get("profit") else 0,
                        "roi": float(fields.get("roi", 0)) if fields.get("roi") else 0,
                    }
            
            print(f"DEBUG: Fetched today's performance data for {len(performance_data)} teams")
            return performance_data
        
        except Exception as e:
            print(f"ERROR: Failed to fetch today's performance: {e}")
            return None
    
    def get_today_projections(self):
        """Fetch today's projections/targets from Lark Base"""
        try:
            records = self.projections_client.list_records()
            today = datetime.now().strftime("%Y-%m-%d")
            
            for record in records:
                fields = self.projections_client.get_record_fields(record)
                record_date = fields.get("projection_date", "")
                
                if record_date == today:
                    return {
                        "revenue_target": float(fields.get("revenue", 0)) if fields.get("revenue") else 0,
                        "spend_target": float(fields.get("spend", 0)) if fields.get("spend") else 0,
                        "profit_target": float(fields.get("profit", 0)) if fields.get("profit") else 0,
                        "roi_target": float(fields.get("roi", 0)) if fields.get("roi") else 0,
                    }
            
            print("DEBUG: No projections found for today")
            return None
        
        except Exception as e:
            print(f"ERROR: Failed to fetch today's projections: {e}")
            return None
    
    def compare_performance_to_targets(self, performance_data, projections_data):
        """Compare performance against targets"""
        comparison = {}
        
        for team, perf in performance_data.items():
            revenue_pct = (perf["revenue"] / projections_data["revenue_target"] * 100) if projections_data["revenue_target"] > 0 else 0
            profit_pct = (perf["profit"] / projections_data["profit_target"] * 100) if projections_data["profit_target"] > 0 else 0
            
            comparison[team] = {
                "revenue_pct": revenue_pct,
                "profit_pct": profit_pct,
                "revenue": perf["revenue"],
                "profit": perf["profit"],
                "revenue_target": projections_data["revenue_target"],
                "profit_target": projections_data["profit_target"]
            }
        
        return comparison
    
    def generate_performance_message(self, team_name, comparison):
        """Generate performance message for a team"""
        if team_name not in comparison:
            return None
        
        comp = comparison[team_name]
        revenue_pct = comp["revenue_pct"]
        profit_pct = comp["profit_pct"]
        revenue = comp["revenue"]
        profit = comp["profit"]
        revenue_target = comp["revenue_target"]
        profit_target = comp["profit_target"]
        
        if revenue_pct >= 100 and profit_pct >= 100:
            message = f"""🎉 **{team_name} - Daily Performance Update**

Fantastic work today! 🚀

📊 **Your Performance:**
• Revenue: ${revenue:,.0f} ({revenue_pct:.0f}% of target) ✅
• Profit: ${profit:,.0f} ({profit_pct:.0f}% of target) ✅

You're crushing your targets! Keep this momentum going! 💪"""
        
        elif revenue_pct >= 100 or profit_pct >= 100:
            message = f"""📈 **{team_name} - Daily Performance Update**

You're making great progress! 💪

📊 **Your Performance:**
• Revenue: ${revenue:,.0f} ({revenue_pct:.0f}% of target)
• Profit: ${profit:,.0f} ({profit_pct:.0f}% of target)

You're on track! Push a little more to hit all your targets today."""
        
        else:
            message = f"""📊 **{team_name} - Daily Performance Update**

Let's finish strong today! 💪

📊 **Your Performance:**
• Revenue: ${revenue:,.0f} ({revenue_pct:.0f}% of target)
• Profit: ${profit:,.0f} ({profit_pct:.0f}% of target)

You've got this! Time to push for those targets! Let's go! 🔥"""
        
        return message
    
    def get_user_data(self):
        """
        Fetch user data from intentt_lark_user_info table
        Returns: Dict mapping email to user info with lark_user_key
        """
        try:
            records = self.projections_client.list_records()
            
            user_data = {}
            for record in records:
                fields = record.get("fields", {})
                email = fields.get("email", "")
                lark_user_key = fields.get("lark_user_key", "")
                name = fields.get("name", "")
                department = fields.get("department", "")
                
                if email and lark_user_key:
                    user_data[email] = {
                        "name": name,
                        "lark_user_key": lark_user_key,
                        "department": department,
                        "email": email
                    }
            
            print(f"DEBUG: Fetched user data for {len(user_data)} users")
            return user_data
        
        except Exception as e:
            print(f"ERROR: Failed to fetch user data: {e}")
            return {}
    
    def get_user_performance(self, campaign_manager_email, target_date=None):
        """
        Get performance for a specific user on a specific date
        If target_date is None, uses today
        """
        try:
            records = self.performance_client.list_records()
            
            if target_date is None:
                target_date = datetime.now().strftime("%Y-%m-%d")
            elif isinstance(target_date, datetime):
                target_date = target_date.strftime("%Y-%m-%d")
            
            for record in records:
                fields = record.get("fields", {})
                record_date = fields.get("date", "")
                record_email = fields.get("campaign_manager", "")
                
                if record_date == target_date and record_email == campaign_manager_email:
                    return {
                        "revenue": float(fields.get("revenue", 0)) if fields.get("revenue") else 0,
                        "spend": float(fields.get("spend", 0)) if fields.get("spend") else 0,
                        "profit": float(fields.get("profit", 0)) if fields.get("profit") else 0,
                        "roi": float(fields.get("roi", 0)) if fields.get("roi") else 0,
                        "date": record_date
                    }
            
            return None
        
        except Exception as e:
            print(f"ERROR: Failed to fetch user performance: {e}")
            return None
    
    def get_daily_user_target(self, target_date=None, num_media_buyers=9):
        """
        Calculate daily profit target per user (total projection / number of media buyers)
        """
        try:
            records = self.projections_client.list_records()
            
            if target_date is None:
                target_date = datetime.now().strftime("%Y-%m-%d")
            elif isinstance(target_date, datetime):
                target_date = target_date.strftime("%Y-%m-%d")
            
            for record in records:
                fields = record.get("fields", {})
                record_date = fields.get("projection_date", "")
                
                if record_date == target_date:
                    return {
                        "revenue_target": (float(fields.get("revenue", 0)) if fields.get("revenue") else 0) / num_media_buyers,
                        "spend_target": (float(fields.get("spend", 0)) if fields.get("spend") else 0) / num_media_buyers,
                        "profit_target": (float(fields.get("profit", 0)) if fields.get("profit") else 0) / num_media_buyers,
                        "roi_target": float(fields.get("roi", 0)) if fields.get("roi") else 0,
                        "date": record_date
                    }
            
            print(f"DEBUG: No projections found for {target_date}")
            return None
        
        except Exception as e:
            print(f"ERROR: Failed to fetch daily user targets: {e}")
            return None
    
    def generate_user_performance_message(self, user_name, user_performance, user_targets):
        """
        Generate personalized message for individual user based on their performance
        """
        if not user_performance or not user_targets:
            return None
        
        revenue_actual = user_performance.get("revenue", 0)
        profit_actual = user_performance.get("profit", 0)
        roi_actual = user_performance.get("roi", 0)
        
        revenue_target = user_targets.get("revenue_target", 0)
        profit_target = user_targets.get("profit_target", 0)
        
        # Calculate percentages
        revenue_pct = (revenue_actual / revenue_target * 100) if revenue_target > 0 else 0
        profit_pct = (profit_actual / profit_target * 100) if profit_target > 0 else 0
        
        revenue_on_pace = revenue_pct >= 100
        profit_on_pace = profit_pct >= 100
        
        # Generate message based on performance
        if revenue_on_pace and profit_on_pace:
            # Exceeding targets - exciting tone
            message = f"""🎉 **{user_name} - Your Daily Performance**

Fantastic work today! 🚀

📊 **Your Performance:**
• Revenue: ${revenue_actual:,.0f} ({revenue_pct:.0f}% of your target) ✅
• Profit: ${profit_actual:,.0f} ({profit_pct:.0f}% of your target) ✅
• ROI: {roi_actual:.1f}%

You're crushing your individual targets! Keep this momentum going! 💪"""
        
        elif revenue_on_pace or profit_on_pace:
            # Partially on pace
            message = f"""📈 **{user_name} - Your Daily Performance**

You're making great progress! 💪

📊 **Your Performance:**
• Revenue: ${revenue_actual:,.0f} ({revenue_pct:.0f}% of your target)
• Profit: ${profit_actual:,.0f} ({profit_pct:.0f}% of your target)
• ROI: {roi_actual:.1f}%

You're on track! Push a little more to hit all your targets today."""
        
        else:
            # Below targets - encouraging tone
            message = f"""📊 **{user_name} - Your Daily Performance**

Let's finish strong today! 💪

📊 **Your Performance:**
• Revenue: ${revenue_actual:,.0f} ({revenue_pct:.0f}% of your target)
• Profit: ${profit_actual:,.0f} ({profit_pct:.0f}% of your target)
• ROI: {roi_actual:.1f}%

You've got this! Time to push for those targets! Let's go! 🔥"""
        
        return message


class LarkBaseClient:
    def __init__(self, app_token, table_id, tenant_access_token, host="https://open.larksuite.com"):
        """
        Initialize Lark Base client
        """
        self.app_token = app_token
        self.table_id = table_id
        self.tenant_access_token = tenant_access_token
        self.host = host
    
    def list_records(self):
        """List all records from the table"""
        try:
            url = f"{self.host}/open-apis/bitable/v1/apps/{self.app_token}/tables/{self.table_id}/records"
            headers = {
                "Authorization": f"Bearer {self.tenant_access_token}",
                "Content-Type": "application/json"
            }
            
            all_records = []
            page_token = None
            
            while True:
                params = {"page_size": 100}
                if page_token:
                    params["page_token"] = page_token
                
                response = requests.get(url, headers=headers, params=params)
                response.raise_for_status()
                
                data = response.json()
                
                if data.get("code") != 0:
                    print(f"ERROR: Lark API error: {data.get('msg')}")
                    break
                
                records = data.get("data", {}).get("items", [])
                all_records.extend(records)
                
                page_token = data.get("data", {}).get("page_token")
                if not page_token:
                    break
            
            return all_records
        
        except Exception as e:
            print(f"ERROR: Failed to list records: {e}")
            return []
    
    def get_record_fields(self, record):
        """Extract fields from a record"""
        return record.get("fields", {})

