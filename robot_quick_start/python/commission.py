import difflib
import re

COMMISSION_RATES = {
    "Ginsu": [
        {"min_spend_ratio": 1.25, "company_rate": 0.11, "buyer_rate": 0.05},
        {"min_spend_ratio": 1.20, "company_rate": 0.09, "buyer_rate": 0.01},
        {"min_spend_ratio": 1.15, "company_rate": 0.06, "buyer_rate": 0.01},
        {"min_spend_ratio": 0.0,  "company_rate": 0.00, "buyer_rate": 0.0},
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

# Platform display names (without "XML" suffix)
PLATFORM_DISPLAY_NAMES = {
    "Ginsu": "Ginsu",
    "Bing XML": "Bing",
    "Yahoo XML": "Yahoo",
    "RSOC": "RSOC",
}

# Aliases for user-friendly input (all lowercase)
SOURCE_ALIASES = {
    "bing": "Bing XML",
    "yahoo": "Yahoo XML",
}

def calculate_commission(text, user_id=None):
    """
    Calculate commission based on sell source and values.
    
    Args:
        text: Input text with source and revenue/spend values
        user_id: Lark user ID (open_id, union_id, or user_id) for @mention
    """
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
        message = f"❌ Invalid source. Available sources: {', '.join(COMMISSION_RATES.keys())}\n\nType and enter 'help' to learn more."
        print(f"DEBUG: calculate_commission returns: {message!r}")
        return message

    # Get display name for platform
    display_name = PLATFORM_DISPLAY_NAMES.get(source, source)

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

        # ROI calculation
        roi_pct = ((revenue - spend) / spend) * 100
        
        # Spend ratio for tier matching
        spend_ratio = revenue / spend

        for tier in COMMISSION_RATES[source]:
            if spend_ratio >= tier["min_spend_ratio"]:
                # Company commission (this is the "company profit")
                company_commission = spend * tier["company_rate"]
                company_rate_pct = tier["company_rate"] * 100
                
                # Buyer commission
                buyer_commission = company_commission * tier["buyer_rate"]
                commission_rate_pct = tier["buyer_rate"] * 100
                
                message = f"""Platform: {display_name}
Spend: ${spend:,.2f}
ROI: {roi_pct:.2f}%
Derived Profit: ${company_commission:,.2f} ({company_rate_pct:.2f}% of spend)
Commission Rate: {commission_rate_pct:.2f}% of company commission
Estimated Commission: ${buyer_commission:,.2f}

Note: This is an estimate and is subject to change depending on the partner's final adjustment."""
                
                print(f"DEBUG: calculate_commission returns: {message!r}")
                return message
                
        message = "❌ No matching commission tier found."
        print(f"DEBUG: calculate_commission returns: {message!r}")
        return message

    else:
        # Profit-based sources (Bing XML, Yahoo XML, RSOC)
        if len(values) < 2:
            message = f"❌ For {source}, please provide revenue and spend. Example: {source} 2000 1500"
            print(f"DEBUG: calculate_commission returns: {message!r}")
            return message

        revenue, spend = values[0], values[1]
        profit = revenue - spend
        
        if spend == 0:
            message = "❌ Spend cannot be zero."
            print(f"DEBUG: calculate_commission returns: {message!r}")
            return message

        # ROI calculation: (Revenue - Spend) / Spend * 100
        roi_pct = ((revenue - spend) / spend) * 100
        
        # Profit % calculation: Profit / Spend * 100
        profit_pct = (profit / spend) * 100

        for tier in COMMISSION_RATES[source]:
            if profit_pct >= tier["min_profit_pct"]:
                buyer_commission = profit * tier["buyer_rate"]
                commission_rate_pct = tier["buyer_rate"] * 100
                
                message = f"""Platform: {display_name}
Spend: ${spend:,.2f}
ROI: {roi_pct:.2f}%
Derived Profit: ${profit:,.2f} ({profit_pct:.2f}% of spend)
Commission Rate: {commission_rate_pct:.2f}% of profit
Estimated Commission: ${buyer_commission:,.2f}

Note: This is an estimate and is subject to change depending on the partner's final adjustment."""
                
                print(f"DEBUG: calculate_commission returns: {message!r}")
                return message
                
        message = "❌ No matching commission tier found."
        print(f"DEBUG: calculate_commission returns: {message!r}")
        return message

def clean_number_string(s):
    """
    Remove dollar signs, commas, and other non-numeric characters except decimal points.
    
    Args:
        s: String that might contain $, commas, etc.
    
    Returns:
        Cleaned string with only numbers and decimal point
    """
    # Remove $, commas, and spaces
    cleaned = s.replace('$', '').replace(',', '').replace(' ', '')
    return cleaned

def is_number(s):
    """
    Check if a string can be converted to a float after cleaning.
    """
    try:
        cleaned = clean_number_string(s)
        float(cleaned)
        return True
    except:
        return False

def parse_number(s):
    """
    Parse a string to float after cleaning dollar signs and commas.
    """
    cleaned = clean_number_string(s)
    return float(cleaned)

def find_source_and_values(text):
    text_lower = text.lower().strip()
    possible_keys = list(COMMISSION_RATES.keys())
    words = text_lower.split()
    
    if not words:
        return None, []
    
    # Check for alias match first (e.g., "bing" → "Bing XML")
    first_word = words[0]
    if first_word in SOURCE_ALIASES:
        matched_key = SOURCE_ALIASES[first_word]
        rest = " ".join(words[1:])
        values = []
        try:
            # Extract numbers from the rest of the text, handling $ and commas
            number_strings = rest.split()
            values = [parse_number(p) for p in number_strings if is_number(p)]
        except Exception as e:
            print(f"DEBUG: Error parsing numbers: {e}")
            return None, []
        return matched_key, values

    # Try matching first 2 words as source (for "Bing XML", "Yahoo XML", etc.)
    if len(words) >= 2:
        candidate = " ".join(words[:2])
        matches = difflib.get_close_matches(candidate, [k.lower() for k in possible_keys], n=1, cutoff=0.8)
        if matches:
            matched_key = next(k for k in possible_keys if k.lower() == matches[0])
            # Use original text to preserve case for number extraction
            rest = text[len(matched_key):].strip()
            values = []
            try:
                # Extract numbers, handling $ and commas
                number_strings = rest.split()
                values = [parse_number(p) for p in number_strings if is_number(p)]
            except Exception as e:
                print(f"DEBUG: Error parsing numbers: {e}")
                return None, []
            return matched_key, values

    # If no match, try first word only
    candidate = words[0]
    matches = difflib.get_close_matches(candidate, [k.lower() for k in possible_keys], n=1, cutoff=0.8)
    if matches:
        matched_key = next(k for k in possible_keys if k.lower() == matches[0])
        # Use original text to preserve case for number extraction
        rest = text[len(matched_key):].strip()
        values = []
        try:
            # Extract numbers, handling $ and commas
            number_strings = rest.split()
            values = [parse_number(p) for p in number_strings if is_number(p)]
        except Exception as e:
            print(f"DEBUG: Error parsing numbers: {e}")
            return None, []
        return matched_key, values

    return None, []

def get_help_message():
    message = """📊 Commission Calculator Help

For Ginsu (based on Spend Ratio = Revenue / Spend):
Provide revenue and spend. Example: `Ginsu 3000 2000` or `Ginsu $3,000 $2,000`

For Bing XML, Yahoo XML, RSOC (based on Profit % = (Revenue - Spend) / Spend):
Provide revenue and spend. Example: `RSOC 2000 1500` or `Bing $2,000 $1,500`

Available Sources:
- Ginsu
- Bing XML (or just "Bing")
- Yahoo XML (or just "Yahoo")
- RSOC

You can use dollar signs ($) and commas (,) in numbers - they will be automatically removed.
"""
    return message

