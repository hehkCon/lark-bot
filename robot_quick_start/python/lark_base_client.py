import requests
import json
from datetime import datetime, timedelta

class LarkBaseClient:
    def __init__(self, app_token, table_id, tenant_access_token, host="https://open.larksuite.com"):
        self.app_token = app_token
        self.table_id = table_id
        self.tenant_access_token = tenant_access_token
        self.host = host
    
    def list_records(self, filter_condition=None):
        """
        Fetch records from a Lark Base table
        filter_condition: Optional filter string for API
        Returns: List of records
        """
        url = f"{self.host}/open-apis/bitable/v1/apps/{self.app_token}/tables/{self.table_id}/records"
        headers = {
            "Authorization": f"Bearer {self.tenant_access_token}",
            "Content-Type": "application/json"
        }
        
        params = {}
        if filter_condition:
            params["filter"] = filter_condition
        
        print(f"DEBUG: Fetching records from Base table {self.table_id}")
        
        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()
            
            if data.get("code") != 0:
                print(f"ERROR: Lark Base API error: {data.get('msg')}")
                return []
            
            records = data.get("data", {}).get("items", [])
            print(f"DEBUG: Fetched {len(records)} records from Base")
            return records
        
        except Exception as e:
            print(f"ERROR: Failed to fetch Base records: {e}")
            return []
    
    def get_record_fields(self, record):
        """Extract field values from a record"""
        return record.get("fields", {})


class PerformanceTracker:
    def __init__(self, app_token, performance_table_id, projections_table_id, tenant_access_token, host="https://open.larksuite.com"):
        self.performance_client = LarkBaseClient(app_token, performance_table_id, tenant_access_token, host)
        self.projections_client = LarkBaseClient(app_token, projections_table_id, tenant_access_token, host)
        self.host = host
    
    def get_today_performance(self):
        """
        Fetch today's performance data from a360_buyer_performance
        Returns: Dict with team performance data
        """
        records = self.performance_client.list_records()
        
        # Get today's date in YYYY-MM-DD format
        today = datetime.now().strftime("%Y-%m-%d")
        
        performance_data = {}
        
        for record in records:
            fields = self.performance_client.get_record_fields(record)
            record_date = fields.get("date", "")
            
            # Match today's date
            if record_date == today:
                team = fields.get("team", "Unknown")
                
                performance_data[team] = {
                    "revenue": float(fields.get("revenue", 0)) if fields.get("revenue") else 0,
                    "spend": float(fields.get("spend", 0)) if fields.get("spend") else 0,
                    "profit": float(fields.get("profit", 0)) if fields.get("profit") else 0,
                    "roi": float(fields.get("roi", 0)) if fields.get("roi") else 0,
                    "intentt_profit": float(fields.get("intentt_profit", 0)) if fields.get("intentt_profit") else 0,
                    "date": record_date
                }
        
        print(f"DEBUG: Today's performance data: {performance_data}")
        return performance_data
    
    def get_today_projections(self):
        """
        Fetch today's projection targets from search_arb_projections_overall
        Returns: Dict with projection targets
        """
        records = self.projections_client.list_records()
        
        # Get today's date in YYYY-MM-DD format
        today = datetime.now().strftime("%Y-%m-%d")
        
        projections_data = {}
        
        for record in records:
            fields = self.projections_client.get_record_fields(record)
            record_date = fields.get("projection_date", "")
            
            # Match today's date
            if record_date == today:
                projections_data = {
                    "revenue_target": float(fields.get("revenue", 0)) if fields.get("revenue") else 0,
                    "spend_target": float(fields.get("spend", 0)) if fields.get("spend") else 0,
                    "profit_target": float(fields.get("profit", 0)) if fields.get("profit") else 0,
                    "roi_target": float(fields.get("roi", 0)) if fields.get("roi") else 0,
                    "date": record_date
                }
        
        print(f"DEBUG: Today's projections: {projections_data}")
        return projections_data
    
    def compare_performance_to_targets(self, performance_data, projections_data):
        """
        Compare team performance against targets
        Returns: Dict with comparison results
        """
        comparison = {}
        
        for team, perf in performance_data.items():
            # Calculate performance metrics
            revenue_pct = (perf["revenue"] / projections_data["revenue_target"] * 100) if projections_data["revenue_target"] > 0 else 0
            spend_pct = (perf["spend"] / projections_data["spend_target"] * 100) if projections_data["spend_target"] > 0 else 0
            profit_pct = (perf["profit"] / projections_data["profit_target"] * 100) if projections_data["profit_target"] > 0 else 0
            
            # Determine if on pace (typically 100% means on target, 100%+ means exceeding)
            is_on_pace_revenue = revenue_pct >= 100
            is_on_pace_profit = profit_pct >= 100
            
            comparison[team] = {
                "revenue": {
                    "actual": perf["revenue"],
                    "target": projections_data["revenue_target"],
                    "percentage": round(revenue_pct, 1),
                    "on_pace": is_on_pace_revenue
                },
                "spend": {
                    "actual": perf["spend"],
                    "target": projections_data["spend_target"],
                    "percentage": round(spend_pct, 1)
                },
                "profit": {
                    "actual": perf["profit"],
                    "target": projections_data["profit_target"],
                    "percentage": round(profit_pct, 1),
                    "on_pace": is_on_pace_profit
                },
                "roi": {
                    "actual": perf["roi"],
                    "target": projections_data["roi_target"]
                },
                "intentt_profit": perf["intentt_profit"]
            }
        
        print(f"DEBUG: Performance comparison: {comparison}")
        return comparison
    
    def generate_performance_message(self, team_name, comparison_data):
        """
        Generate an encouraging or exciting message based on performance
        """
        team_data = comparison_data.get(team_name, {})
        
        revenue_on_pace = team_data.get("revenue", {}).get("on_pace", False)
        profit_on_pace = team_data.get("profit", {}).get("on_pace", False)
        
        revenue_pct = team_data.get("revenue", {}).get("percentage", 0)
        profit_pct = team_data.get("profit", {}).get("percentage", 0)
        revenue_actual = team_data.get("revenue", {}).get("actual", 0)
        profit_actual = team_data.get("profit", {}).get("actual", 0)
        roi_actual = team_data.get("roi", {}).get("actual", 0)
        
        # Build message
        if revenue_on_pace and profit_on_pace:
            # Exceeding targets - exciting tone
            message = f"""🎉 **{team_name} - Daily Performance Update**

You're crushing it today! 🚀

📊 **Today's Performance:**
• Revenue: ${revenue_actual:,.0f} ({revenue_pct}% of target) ✅
• Profit: ${profit_actual:,.0f} ({profit_pct}% of target) ✅
• ROI: {roi_actual:.1f}%

Keep up the momentum! You're on pace to exceed today's targets! 💪"""
        
        elif revenue_on_pace or profit_on_pace:
            # Partially on pace - neutral/encouraging tone
            message = f"""📈 **{team_name} - Daily Performance Update**

You're making good progress! 💪

📊 **Today's Performance:**
• Revenue: ${revenue_actual:,.0f} ({revenue_pct}% of target)
• Profit: ${profit_actual:,.0f} ({profit_pct}% of target)
• ROI: {roi_actual:.1f}%

You're on track! Keep pushing to hit all your targets today."""
        
        else:
            # Below targets - encouraging tone
            message = f"""📊 **{team_name} - Daily Performance Update**

Let's finish strong today! 💪

📊 **Today's Performance:**
• Revenue: ${revenue_actual:,.0f} ({revenue_pct}% of target)
• Profit: ${profit_actual:,.0f} ({profit_pct}% of target)
• ROI: {roi_actual:.1f}%

You've got this! Time to push for those targets! Let's go! 🔥"""
        
        return message

