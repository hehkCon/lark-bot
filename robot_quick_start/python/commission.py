import json

COMMISSION_RATES = {
    "Ginsu": [
        {"min_spend_ratio": 1.25, "company_rate": 0.11, "buyer_rate": 0.05},
        {"min_spend_ratio": 1.20, "company_rate": 0.09, "buyer_rate": 0.01},
        {"min_spend_ratio": 1.15, "company_rate": 0.06, "buyer_rate": 0.01},
        {"min_spend_ratio": 0.0,  "company_rate": 0.00, "buyer_rate": 0.0},  # below 1.15 no buyer commission
    ],
    # Profit-based sources have same tiers and buyer commissions
    "Bing XML": [
        {"min_profit_pct": 10, "buyer_rate": 0.05},
        {"min_profit_pct": 0,  "buyer_rate": 0.01},
    ],
    "Yahoo XML": [
        {"min_profit_pct": 10, "buyer_rate": 0.05},
        {"min_profit_pct": 0,  "buyer_rate": 0.01},
    ],
    "RSOC": [
        {"min_profit_pct": 10, "buyer_rate": 0.05},
        {"min_profit_pct": 0,  "buyer_rate": 0.01},
    ],
}

def calculate_commission(text):
    text = text.strip()
    parts = text.split()

    if len(parts) < 3:
        return get_help_message()

    # Extract source and numeric values
    source_input = parts[0]
    values = []
    try:
        values = [float(p) for p in parts[1:] if is_number(p)]
    except:
        return json.dumps({"text": "❌ Invalid numeric input."})

    source = None
    for key in COMMISSION_RATES.keys():
        if source_input.lower() == key.lower():
            source = key
            break

    if not source:
        return json.dumps({"text": f"❌ Invalid source '{source_input}'. Available sources: {', '.join(COMMISSION_RATES.keys())}"})

    if source == "Ginsu":
        if len(values) < 2:
            return json.dumps({"text": f"❌ For {source}, please provide revenue and spend. Example: {source} 3000 2000"})
        revenue, spend = values[0], values[1]
        if spend == 0:
            return json.dumps({"text": "❌ Spend cannot be zero."})

        spend_ratio = revenue / spend

        for tier in COMMISSION_RATES[source]:
            if spend_ratio >= tier["min_spend_ratio"]:
                company_commission = spend * tier["company_rate"]
                buyer_commission = company_commission * tier["buyer_rate"]
                if buyer_commission == 0:
                    message = f"Buyer commission is 0 for spend ratio {spend_ratio:.3f}."
                else:
                    message = f"Buyer commission: ${buyer_commission:,.2f}"
                return json.dumps({"text": message})
        return json.dumps({"text": "❌ No matching commission tier found."})

    # For profit-based sources
    else:
        if len(values) < 2:
            return json.dumps({"text": f"❌ For {source}, please provide revenue and spend. Example: {source} 2000 1500"})
        revenue, spend = values[0], values[1]
        profit = revenue - spend
        if revenue == 0:
            return json.dumps({"text": "❌ Revenue cannot be zero."})

        profit_pct = (profit / revenue) * 100

        for tier in COMMISSION_RATES[source]:
            if profit_pct >= tier["min_profit_pct"]:
                buyer_commission = profit * tier["buyer_rate"]
                if buyer_commission <= 0:
                    message = f"Buyer commission is 0 for profit percentage {profit_pct:.2f}%."
                else:
                    message = f"Buyer commission: ${buyer_commission:,.2f}"
                return json.dumps({"text": message})
        return json.dumps({"text": "❌ No matching commission tier found."})

def is_number(s):
    try:
        float(s)
        return True
    except:
        return False

def get_help_message():
    message = """📊 Commission Calculator Help

For Ginsu (based on Spend Ratio = Revenue / Spend):
Provide revenue and spend. Example: `Ginsu 3000 2000`

For Bing XML, Yahoo XML, RSOC (based on Profit % = (Revenue - Spend) / Revenue):
Provide revenue and spend. Example: `RSOC 2000 1500`

Available Sources:
- Ginsu
- Bing XML
- Yahoo XML
- RSOC
"""
    return json.dumps({"text": message})

