import difflib

COMMISSION_RATES = {
    "Ginsu": [
        {"min_spend_ratio": 1.25, "company_rate": 0.11, "buyer_rate": 0.05},
        {"min_spend_ratio": 1.20, "company_rate": 0.09, "buyer_rate": 0.01},
        {"min_spend_ratio": 1.15, "company_rate": 0.06, "buyer_rate": 0.01},
        {"min_spend_ratio": 0.0,  "company_rate": 0.00, "buyer_rate": 0.0},  # below 1.15 no buyer commission
    ],
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
    if text.lower() == "help":
        message = get_help_message()
        print(f"DEBUG: calculate_commission returns: {message!r}")
        return message

    if len(text) == 0:
        message = get_help_message()
        print(f"DEBUG: calculate_commission returns: {message!r}")
        return message

    source, values = find_source_and_values(text)
    if not source:
        message = f"❌ Invalid source. Available sources: {', '.join(COMMISSION_RATES.keys())}"
        print(f"DEBUG: calculate_commission returns: {message!r}")
        return message

    if source == "Ginsu":
        if len(values) < 2:
            message = f"❌ For {source}, please provide revenue and spend. Example: {source} 3000 2000"
            print(f"DEBUG: calculate_commission returns: {message!r}")
            return message

        revenue, spend = values[0], values[1]
        if spend == 0:
            message = "❌ Spend cannot be zero."
            print(f"DEBUG: calculate_commission returns: {message!r}")
            return message

        spend_ratio = revenue / spend

        for tier in COMMISSION_RATES[source]:
            if spend_ratio >= tier["min_spend_ratio"]:
                company_commission = spend * tier["company_rate"]
                buyer_commission = company_commission * tier["buyer_rate"]
                if buyer_commission == 0:
                    message = f"{source}: Buyer commission is $0"
                else:
                    message = f"{source}: Buyer commission: ${buyer_commission:,.2f}"
                print(f"DEBUG: calculate_commission returns: {message!r}")
                return message
        message = "❌ No matching commission tier found."
        print(f"DEBUG: calculate_commission returns: {message!r}")
        return message

    else:
        # Profit-based sources
        if len(values) < 2:
            message = f"❌ For {source}, please provide revenue and spend. Example: {source} 2000 1500"
            print(f"DEBUG: calculate_commission returns: {message!r}")
            return message

        revenue, spend = values[0], values[1]
        profit = revenue - spend
        if revenue == 0:
            message = "❌ Revenue cannot be zero."
            print(f"DEBUG: calculate_commission returns: {message!r}")
            return message

        profit_pct = (profit / revenue) * 100

        for tier in COMMISSION_RATES[source]:
            if profit_pct >= tier["min_profit_pct"]:
                buyer_commission = profit * tier["buyer_rate"]
                if buyer_commission <= 0:
                    message = f"{source}: Buyer commission is $0"
                else:
                    message = f"{source}: Buyer commission: ${buyer_commission:,.2f}"
                print(f"DEBUG: calculate_commission returns: {message!r}")
                return message
        message = "❌ No matching commission tier found."
        print(f"DEBUG: calculate_commission returns: {message!r}")
        return message

def find_source_and_values(text):
    text_lower = text.lower()
    possible_keys = list(COMMISSION_RATES.keys())
    words = text_lower.split()

    # Try matching first 2 words as source
    candidate = " ".join(words[:2])
    matches = difflib.get_close_matches(candidate, [k.lower() for k in possible_keys], n=1, cutoff=0.8)
    if matches:
        matched_key = next(k for k in possible_keys if k.lower() == matches[0])
        rest = text[len(matched_key):].strip()
        parts_rest = rest.split()
        values = []
        try:
            values = [float(p) for p in parts_rest if is_number(p)]
        except:
            return None, []
        return matched_key, values

    # If no match, try first word only
    candidate = words[0]
    matches = difflib.get_close_matches(candidate, [k.lower() for k in possible_keys], n=1, cutoff=0.8)
    if matches:
        matched_key = next(k for k in possible_keys if k.lower() == matches[0])
        rest = text[len(matched_key):].strip()
        parts_rest = rest.split()
        values = []
        try:
            values = [float(p) for p in parts_rest if is_number(p)]
        except:
            return None, []
        return matched_key, values

    return None, []

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
    return message

