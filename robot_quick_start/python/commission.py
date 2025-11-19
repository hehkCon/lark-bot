import re
import json

# Commission rate configuration
COMMISSION_RATES = {
    "Ginsu": [
        {"min_spend_pct": 25, "max_spend_pct": 100, "revenue_rate": 11, "buyer_commission": 5, "calc_type": "Spend %"},
        {"min_spend_pct": 20, "max_spend_pct": 24.99, "revenue_rate": 9, "buyer_commission": 1, "calc_type": "Spend %"},
        {"min_spend_pct": 15, "max_spend_pct": 19.99, "revenue_rate": 6, "buyer_commission": 1, "calc_type": "Spend %"},
        {"min_spend_pct": 0, "max_spend_pct": 14.99, "revenue_rate": 2, "buyer_commission": 0, "calc_type": "Spend %"},
    ],
    "Bing XML": [
        {"min_profit": 10, "max_profit": 100, "revenue_rate": 5, "calc_type": "Profit"},
        {"min_profit": 0, "max_profit": 9.99, "revenue_rate": 1, "calc_type": "Profit"},
    ],
    "Yahoo XML": [
        {"min_profit": 10, "max_profit": 100, "revenue_rate": 5, "calc_type": "Profit"},
        {"min_profit": 0, "max_profit": 9.99, "revenue_rate": 1, "calc_type": "Profit"},
    ],
    "RSOC": [
        {"min_profit": 10, "max_profit": 100, "revenue_rate": 5, "calc_type": "Profit"},
        {"min_profit": 0, "max_profit": 9.99, "revenue_rate": 1, "calc_type": "Profit"},
    ],
}

def calculate_commission(text):
    """
    Parse user message and calculate commission.
    Expected format examples:
    - "Ginsu 1000 200" (source, revenue, spend)
    - "Bing XML 500" (source, profit)
    - "calc Ginsu 1000 200"
    """
    
    # Clean and parse input
    text = text.strip()
    
    # Try to extract source, revenue, and spend/profit
    parts = text.split()
    
    if len(parts) < 2:
        return get_help_message()
    
    # Determine source (support multi-word sources like "Bing XML")
    source = None
    values = []
    
    for key in COMMISSION_RATES.keys():
        if text.lower().startswith(key.lower()):
            source = key
            remaining = text[len(key):].strip().split()
            values = [float(v) for v in remaining if is_number(v)]
            break
    
    if not source:
        error_msg = f"❌ Invalid source. Available sources: {', '.join(COMMISSION_RATES.keys())}\n\n{get_help_message()}"
        return json.dumps({"text": error_msg})
    
    # Calculate based on source type
    rate_config = COMMISSION_RATES[source]
    calc_type = rate_config[0]["calc_type"]
    
    if calc_type == "Spend %":
        if len(values) < 2:
            error_msg = f"❌ For {source}, please provide: revenue and spend\nExample: {source} 1000 200"
            return json.dumps({"text": error_msg})
        
        revenue = values[0]
        spend = values[1]
        spend_pct = (spend / revenue * 100) if revenue > 0 else 0
        
        # Find matching tier
        matching_tier = None
        for tier in rate_config:
            if tier["min_spend_pct"] <= spend_pct <= tier["max_spend_pct"]:
                matching_tier = tier
                break
        
        if not matching_tier:
            error_msg = f"❌ No matching commission tier for {spend_pct:.2f}% spend"
            return json.dumps({"text": error_msg})
        
        commission = revenue * (matching_tier["revenue_rate"] / 100)
        buyer_commission = revenue * (matching_tier["buyer_commission"] / 100)
        
        return format_result(source, revenue, spend, spend_pct, commission, buyer_commission, matching_tier)
    
    elif calc_type == "Profit":
        if len(values) < 1:
            error_msg = f"❌ For {source}, please provide: profit\nExample: {source} 50"
            return json.dumps({"text": error_msg})
        
        profit = values[0]
        
        # Find matching tier
        matching_tier = None
        for tier in rate_config:
            if tier["min_profit"] <= profit <= tier["max_profit"]:
                matching_tier = tier
                break
        
        if not matching_tier:
            error_msg = f"❌ No matching commission tier for ${profit:.2f} profit"
            return json.dumps({"text": error_msg})
        
        commission = profit * (matching_tier["revenue_rate"] / 100)
        
        return format_profit_result(source, profit, commission, matching_tier)
    
    return json.dumps({"text": "❌ Unknown calculation type"})

def is_number(s):
    try:
        float(s)
        return True
    except ValueError:
        return False

def format_result(source, revenue, spend, spend_pct, commission, buyer_commission, tier):
    message = f"""✅ Commission Calculation

Source: {source}
Revenue: ${revenue:,.2f}
Spend: ${spend:,.2f}
Spend %: {spend_pct:.2f}%

Commission Tier: {tier['revenue_rate']}% revenue
Your Commission: ${commission:,.2f}
Buyer Commission: ${buyer_commission:,.2f}
Total Payout: ${commission + buyer_commission:,.2f}
"""
    return json.dumps({"text": message})

def format_profit_result(source, profit, commission, tier):
    message = f"""✅ Commission Calculation

Source: {source}
Profit: ${profit:,.2f}

Commission Tier: {tier['revenue_rate']}% of profit
Your Commission: ${commission:,.2f}
"""
    return json.dumps({"text": message})

def get_help_message():
    message = """📊 Commission Calculator Help

For Ginsu (Spend % based):
Ginsu [revenue] [spend]
Example: Ginsu 1000 200

For Bing XML, Yahoo XML, RSOC (Profit based):
[Source] [profit]
Example: Bing XML 50

Available Sources:
- Ginsu
- Bing XML
- Yahoo XML
- RSOC
"""
    return json.dumps({"text": message})
