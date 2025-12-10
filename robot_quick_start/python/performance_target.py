"""
Performance Target Tracker for Lark Bot
Compares actual performance against projections from Lark Base
"""

from datetime import datetime
import pytz


class PerformanceTarget:
    """Handler for performance target comparisons"""
    
    def __init__(self, lark_base_client, performance_tracker):
        """
        Initialize PerformanceTarget handler
        
        Args:
            lark_base_client: LarkBase API client for querying tables
            performance_tracker: PerformanceTracker instance for actual data
        """
        self.lark_client = lark_base_client
        self.tracker = performance_tracker
        self.montreal_tz = pytz.timezone('America/Toronto')
        
        # Table IDs from Lark Base
        self.projection_table_id = "tblMhyHMr7A4qEhQ"
        self.performance_table_id = "tblQuLH08cVG4ber"
    
    def get_projection_data(self, start_date_str, end_date_str):
        """
        Fetch projection data from Lark Base table
        
        Args:
            start_date_str: Start date as "YYYY-MM-DD"
            end_date_str: End date as "YYYY-MM-DD"
        
        Returns:
            Dict with aggregated metrics or error message
        """
        try:
            print(f"DEBUG: Fetching projections from {start_date_str} to {end_date_str}")
            
            # Query projection table
            records = self.lark_client.get_table_records(self.projection_table_id)
            print(f"DEBUG: Got {len(records)} total projection records")
            
            if not records:
                print("DEBUG: No projection records found!")
                return {
                    "success": False,
                    "error": "⚠️  No projection data found in table",
                    "records_found": 0
                }
            
            # Filter by date range and aggregate
            matching_dates = []
            total_revenue = 0
            total_spend = 0
            total_profit = 0
            
            for record in records:
                fields = record.get("fields", {})
                
                # Extract projection_date
                projection_date_field = fields.get("projection_date")
                if not projection_date_field:
                    continue
                
                projection_date = self._extract_date_string(projection_date_field)
                if not projection_date:
                    continue
                
                # Check if date is in range
                if not (start_date_str <= projection_date <= end_date_str):
                    print(f"DEBUG: Projection date {projection_date} outside range")
                    continue
                
                # Extract metrics
                try:
                    revenue = float(fields.get("revenue", 0) or 0)
                    spend = float(fields.get("spend", 0) or 0)
                    profit = float(fields.get("profit", 0) or 0)
                    
                    total_revenue += revenue
                    total_spend += spend
                    total_profit += profit
                    matching_dates.append(projection_date)
                    
                    print(f"DEBUG: Projection {projection_date}: R=${revenue}, S=${spend}, P=${profit}")
                except (ValueError, TypeError) as e:
                    print(f"DEBUG: Error parsing metrics for {projection_date}: {e}")
                    continue
            
            if not matching_dates:
                print(f"DEBUG: ⚠️  No projection dates found in range {start_date_str} to {end_date_str}")
                return {
                    "success": False,
                    "error": f"⚠️  No projection data found for dates {start_date_str} to {end_date_str}",
                    "records_found": 0
                }
            
            # Calculate ROI
            roi = (total_profit / total_spend * 100) if total_spend > 0 else 0
            
            print(f"DEBUG: Projection summary - {len(matching_dates)} days")
            print(f"DEBUG: R=${total_revenue:,.0f}, S=${total_spend:,.0f}, P=${total_profit:,.0f}, ROI={roi:.1f}%")
            
            return {
                "success": True,
                "revenue": total_revenue,
                "spend": total_spend,
                "profit": total_profit,
                "roi": roi,
                "days_count": len(matching_dates),
                "records_found": len(matching_dates)
            }
        
        except Exception as e:
            print(f"ERROR in get_projection_data: {e}")
            return {
                "success": False,
                "error": f"❌ Error fetching projection data: {str(e)}",
                "records_found": 0
            }
    
    def get_actual_vs_target(self, actual_data, projection_data):
        """
        Calculate variance between actual and target
        
        Args:
            actual_data: Dict with actual metrics (revenue, spend, profit, roi, days_with_data)
            projection_data: Dict with target metrics (revenue, spend, profit, roi, days_count)
        
        Returns:
            Dict with comparison results
        """
        if not actual_data.get("success") or not projection_data.get("success"):
            return {
                "success": False,
                "error": "Unable to compare: missing data"
            }
        
        try:
            actual_revenue = actual_data["revenue"]
            actual_spend = actual_data["spend"]
            actual_profit = actual_data["profit"]
            actual_roi = actual_data["roi"]
            
            target_revenue = projection_data["revenue"]
            target_spend = projection_data["spend"]
            target_profit = projection_data["profit"]
            target_roi = projection_data["roi"]
            
            # Calculate variance (actual - target)
            rev_variance = actual_revenue - target_revenue
            rev_variance_pct = (rev_variance / target_revenue * 100) if target_revenue > 0 else 0
            
            spend_variance = actual_spend - target_spend
            spend_variance_pct = (spend_variance / target_spend * 100) if target_spend > 0 else 0
            
            profit_variance = actual_profit - target_profit
            profit_variance_pct = (profit_variance / target_profit * 100) if target_profit > 0 else 0
            
            roi_variance = actual_roi - target_roi
            roi_variance_pct = (roi_variance / target_roi * 100) if target_roi > 0 else 0
            
            print(f"DEBUG: Variance calculated")
            print(f"DEBUG: Revenue var: ${rev_variance:,.0f} ({rev_variance_pct:+.1f}%)")
            print(f"DEBUG: Spend var: ${spend_variance:,.0f} ({spend_variance_pct:+.1f}%)")
            print(f"DEBUG: Profit var: ${profit_variance:,.0f} ({profit_variance_pct:+.1f}%)")
            print(f"DEBUG: ROI var: {roi_variance:+.1f}% ({roi_variance_pct:+.1f}%)")
            
            return {
                "success": True,
                "actual": {
                    "revenue": actual_revenue,
                    "spend": actual_spend,
                    "profit": actual_profit,
                    "roi": actual_roi,
                    "days": actual_data.get("days_with_data", 0)
                },
                "target": {
                    "revenue": target_revenue,
                    "spend": target_spend,
                    "profit": target_profit,
                    "roi": target_roi,
                    "days": projection_data.get("days_count", 0)
                },
                "variance": {
                    "revenue": rev_variance,
                    "revenue_pct": rev_variance_pct,
                    "spend": spend_variance,
                    "spend_pct": spend_variance_pct,
                    "profit": profit_variance,
                    "profit_pct": profit_variance_pct,
                    "roi": roi_variance,
                    "roi_pct": roi_variance_pct
                }
            }
        
        except Exception as e:
            print(f"ERROR in get_actual_vs_target: {e}")
            return {
                "success": False,
                "error": f"Error calculating variance: {str(e)}"
            }
    
    def format_comparison(self, comparison_data, period_name, actual_min_date, actual_max_date):
        """
        Format comparison as response message with motivational messages
        
        Args:
            comparison_data: Dict with comparison results
            period_name: String like "December 3-9, 2025"
            actual_min_date: Actual min date from data (for display)
            actual_max_date: Actual max date from data (for display)
        
        Returns:
            Formatted response string
        """
        if not comparison_data.get("success"):
            return comparison_data.get("error", "❌ Unable to format comparison")
        
        actual = comparison_data["actual"]
        target = comparison_data["target"]
        variance = comparison_data["variance"]
        
        # Determine status based on profit variance
        profit_var = variance["profit"]
        profit_var_pct = variance["profit_pct"]
        
        if profit_var >= 0:
            # ✅ Exceeding or meeting target - congratulatory
            status = "✅ **Performance Target (On Track!)**"
            if profit_var_pct > 10:
                motivation = "🎉 Crushing it team!"
            elif profit_var_pct > 0:
                motivation = "👏 Exceeding targets!"
            else:
                motivation = "✅ On target"
        else:
            # ❌ Underperforming - encouraging message
            status = "⚠️  **Performance Target (Needs Attention)**"
            if profit_var_pct > -20:
                motivation = "💪 Close to target!"
            else:
                motivation = "🚀 Refocus needed"
        
        # Format date range
        if actual_min_date and actual_max_date:
            date_range = f"({actual_min_date} to {actual_max_date})"
        else:
            date_range = f"(Period: {period_name})"
        
        response = f"""{status} {date_range}
{motivation}

**Revenue:**
Actual: ${actual['revenue']:,.0f}
Target: ${target['revenue']:,.0f}
Variance: ${variance['revenue']:+,.0f} ({variance['revenue_pct']:+.1f}%)

**Spend:**
Actual: ${actual['spend']:,.0f}
Target: ${target['spend']:,.0f}
Variance: ${variance['spend']:+,.0f} ({variance['spend_pct']:+.1f}%)

**Profit:**
Actual: ${actual['profit']:,.0f}
Target: ${target['profit']:,.0f}
Variance: ${variance['profit']:+,.0f} ({variance['profit_pct']:+.1f}%)

**ROI:**
Actual: {actual['roi']:.1f}%
Target: {target['roi']:.1f}%
Variance: {variance['roi']:+.1f}% ({variance['roi_pct']:+.1f}%)

📊 Days analyzed: {actual['days']}"""
        
        return response
    
    def _extract_date_string(self, field_value):
        """
        Extract date string from Lark field value
        
        Args:
            field_value: Can be string "YYYY-MM-DD" or dict with "timestamp"
        
        Returns:
            Date string "YYYY-MM-DD" or None
        """
        if isinstance(field_value, str):
            # Try to extract YYYY-MM-DD format
            if len(field_value) >= 10:
                return field_value[:10]
            return None
        elif isinstance(field_value, dict):
            # Might be timestamp format
            timestamp = field_value.get("timestamp")
            if timestamp:
                try:
                    dt = datetime.fromtimestamp(timestamp / 1000, tz=self.montreal_tz)
                    return dt.strftime("%Y-%m-%d")
                except (ValueError, TypeError):
                    return None
        return None
