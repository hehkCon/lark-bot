# creative_tracker.py - UPDATED WITH DYNAMIC PAYMENT RATES BY ROLE

import re
import os
from datetime import datetime
from calendar import monthrange
from meegle_api import MeegleClient


# User ID mapping for content creators
CREATOR_USER_IDS = {
    "aure": "7569613836605492757",
    "aure williams": "7569613836605492757",
    "alejandra": "7566221514945662485",
    "7562186989836045843": "7562186989836045843",
    "carolina": "7581455452412628499",
}


# Payment rates by role (in dollars per video)
PAYMENT_RATES_BY_ROLE = {
    "creator": 13.00,
    "video_editor": 5.50,
}


# Default payment rate if role not found
DEFAULT_PAYMENT_RATE = 13.00


def get_user_data_from_lark(lark_base_client, users_table_id):
    """
    Fetch all users from Lark Base and build a lookup dictionary
    
    Args:
        lark_base_client: LarkBaseClient instance
        users_table_id: Table ID for users table (from .env)
    
    Returns:
        Dictionary keyed by email with user info (name, role, department, etc.)
    """
    try:
        print(f"DEBUG: Fetching users from Lark Base table: {users_table_id}")
        
        # Get all records from users table
        all_records = lark_base_client._search_records(users_table_id)
        print(f"DEBUG: Got {len(all_records)} total user records")
        
        user_data = {}
        
        for record in all_records:
            fields = record.get("fields", {})
            
            # Extract user info
            email = fields.get("email", "").lower() if fields.get("email") else None
            name = fields.get("name", "")
            role = fields.get("role", "")
            department = fields.get("department", "")
            
            if email:
                user_data[email] = {
                    "name": name,
                    "role": role,
                    "department": department,
                    "record_id": record.get("record_id")
                }
                print(f"DEBUG: Loaded user {email} - role: {role}, department: {department}")
        
        print(f"DEBUG: Successfully loaded {len(user_data)} users from Lark Base")
        return user_data
        
    except Exception as e:
        print(f"ERROR in get_user_data_from_lark: {e}")
        import traceback
        print(traceback.format_exc())
        return {}


def get_payment_rate_for_user(creator_name, user_data):
    """
    Get payment rate based on user's role from user_data table
    
    Args:
        creator_name: Name or email of the creator
        user_data: Dictionary of users keyed by email (from Lark Base)
    
    Returns:
        Payment rate in dollars (float)
    """
    if not user_data:
        print(f"DEBUG: user_data is None, using default rate ${DEFAULT_PAYMENT_RATE}")
        return DEFAULT_PAYMENT_RATE
    
    # Try to find the user in user_data
    creator_lower = creator_name.lower()
    
    # First try exact email match
    if creator_lower in user_data:
        user_info = user_data[creator_lower]
        role = user_info.get("role", "").lower()
        rate = PAYMENT_RATES_BY_ROLE.get(role, DEFAULT_PAYMENT_RATE)
        print(f"DEBUG: Found {creator_name} with role '{role}', rate: ${rate}")
        return rate
    
    # Try name match
    for email, info in user_data.items():
        name = info.get("name", "").lower()
        if creator_lower in name or name in creator_lower:
            role = info.get("role", "").lower()
            rate = PAYMENT_RATES_BY_ROLE.get(role, DEFAULT_PAYMENT_RATE)
            print(f"DEBUG: Found {creator_name} (email: {email}) with role '{role}', rate: ${rate}")
            return rate
    
    # User not found, use default
    print(f"DEBUG: {creator_name} not found in user_data, using default rate ${DEFAULT_PAYMENT_RATE}")
    return DEFAULT_PAYMENT_RATE


def parse_creative_command(text):
    text_lower = text.lower().strip()
    if not text_lower.startswith("creative"):
        return None
    parts = text.split()
    if len(parts) == 2 and parts[1].lower() == "help":
        return {"type": "help"}
    if len(parts) == 2 and parts[1].lower() == "test":
        return {"type": "test"}
    if len(parts) < 3:
        return {"error": "Invalid creative command. Type 'creative help' for usage."}
    command_type = parts[1].lower()
    if command_type in ["count", "stats"]:
        creator_name = parts[2]
        time_period = " ".join(parts[3:]) if len(parts) > 3 else "this month"
        return {"type": command_type, "creator": creator_name, "time_period": time_period}
    elif command_type == "payment":
        creator_name = parts[2]
        time_period = " ".join(parts[3:]) if len(parts) > 3 else "this month"
        return {"type": "payment", "creator": creator_name, "time_period": time_period}
    elif command_type == "language":
        language = parts[2]
        time_period = " ".join(parts[3:]) if len(parts) > 3 else "this month"
        return {"type": "language", "language": language, "time_period": time_period}
    return {"error": f"Unknown creative command: {command_type}. Type 'creative help' for usage."}


def parse_time_period(time_period_str):
    now = datetime.now()
    time_lower = time_period_str.lower()
    if "this month" in time_lower:
        start_date = datetime(now.year, now.month, 1)
        last_day = monthrange(now.year, now.month)[1]
        end_date = datetime(now.year, now.month, last_day, 23, 59, 59)
        period_name = now.strftime("%B %Y")
    elif "last month" in time_lower or "month" in time_lower and "this" not in time_lower:
        if now.month == 1:
            month, year = 12, now.year - 1
        else:
            month, year = now.month - 1, now.year
        start_date = datetime(year, month, 1)
        last_day = monthrange(year, month)[1]
        end_date = datetime(year, month, last_day, 23, 59, 59)
        period_name = start_date.strftime("%B %Y")
    else:
        month_names = {
            "january": 1, "february": 2, "march": 3, "april": 4,
            "may": 5, "june": 6, "july": 7, "august": 8,
            "september": 9, "october": 10, "november": 11, "december": 12
        }
        for month_name, month_num in month_names.items():
            if month_name in time_lower:
                year = now.year
                year_match = re.search(r'20\d{2}', time_period_str)
                if year_match:
                    year = int(year_match.group())
                start_date = datetime(year, month_num, 1)
                last_day = monthrange(year, month_num)[1]
                end_date = datetime(year, month_num, last_day, 23, 59, 59)
                period_name = start_date.strftime("%B %Y")
                break
        else:
            start_date = datetime(now.year, now.month, 1)
            last_day = monthrange(now.year, now.month)[1]
            end_date = datetime(now.year, now.month, last_day, 23, 59, 59)
            period_name = now.strftime("%B %Y")
    return start_date, end_date, period_name


def count_creatives_by_creator(creator_name, time_period_str, lark_user_id=None):
    """Returns formatted response with creative count (original function)"""
    client = MeegleClient()
    start_date, end_date, period_name = parse_time_period(time_period_str)
    start_timestamp = int(start_date.timestamp() * 1000)
    end_timestamp = int(end_date.timestamp() * 1000)
    print(f"DEBUG: Period: {period_name}")
    print(f"DEBUG: Start timestamp: {start_timestamp} ({start_date})")
    print(f"DEBUG: End timestamp: {end_timestamp} ({end_date})")
    if creator_name.lower() in ["me", "i"]:
        creator_name = get_meegle_username_from_lark(lark_user_id)
        if not creator_name:
            return f"❌ Could not find your Meegle username. Please use your Meegle name instead."
    creator_lookup = creator_name.lower()
    creator_user_id = CREATOR_USER_IDS.get(creator_lookup)
    if not creator_user_id:
        return f"❌ Could not find user ID for '{creator_name}'. Known creators: {', '.join([k.title() for k in CREATOR_USER_IDS.keys() if not k.isdigit()])}"
    print(f"DEBUG: Searching for creator '{creator_name}' with user_id: {creator_user_id}")

    valid_statuses = [
        "Compliance Review",
        "Rejected Creative - Revision",
        "Ready To Launch",
        "Creative Performance Monitoring"
    ]
    try:
        result = client.search_work_items(filters=None)
        all_items = result.get("data", [])
        print(f"DEBUG: Got {len(all_items)} total work items")
        filtered_items = []
        for item in all_items:
            item_id = item.get('id')
            item_name = item.get('name')
            fields = item.get("fields", [])
            creator_matched = False
            found_creator_value = None
            for field in fields:
                if field.get("field_alias") == "content_creator":
                    creator_value = str(field.get("field_value", ""))
                    found_creator_value = creator_value
                    print(f"DEBUG: Item {item_id} content_creator={creator_value} (want {creator_user_id})")
                    if creator_user_id == creator_value:
                        creator_matched = True
                        break
            if not creator_matched:
                print(f"DEBUG: Item {item_id} - SKIPPED: creator did not match (found {found_creator_value})")
                continue
            state_times = item.get("state_times", [])
            matched_state = False
            for state in state_times:
                state_name = state.get("name", "")
                end_time = state.get("end_time", 0)
                print(f"DEBUG: Item {item_id} state_name={state_name} end_time={end_time}")
                if state_name == "Creative Production" and end_time > 0:
                    if start_timestamp <= end_time <= end_timestamp:
                        filtered_items.append(item)
                        matched_state = True
                        completion_date = datetime.fromtimestamp(end_time / 1000)
                        print(f"DEBUG: ✅ COUNTED item {item_id} for period - exited Creative Production at {completion_date}")
                    else:
                        print(f"DEBUG: Item {item_id} - Creative Production exit out of period")
            if not matched_state:
                print(f"DEBUG: Item {item_id} - DID NOT FIND valid Creative Production end time in period")
        response = f"""📊 Creative Stats for {creator_name.title()}


Period: {period_name}
Total Creatives Completed: {len(filtered_items)}


Counted: Items that exited Creative Production during {period_name}
Current statuses:
• Compliance Review
• Rejected Creative - Revision
• Ready To Launch
• Creative Performance Monitoring"""
        return response
    except Exception as e:
        import traceback
        print(f"ERROR: Meegle API error: {e}")
        print(f"Traceback: {traceback.format_exc()}")
        return f"❌ Error fetching creative data: {str(e)}"


def get_creator_count_and_payment(creator_name, time_period_str, user_data=None, lark_user_id=None):
    """
    Returns dict with creator count and payment calculation
    
    Args:
        creator_name: Name of the creator
        time_period_str: Time period string (e.g., "this month")
        user_data: Dictionary of users from Lark Base (for role lookup)
        lark_user_id: Lark user ID (optional, for "me" command)
    """
    client = MeegleClient()
    start_date, end_date, period_name = parse_time_period(time_period_str)
    start_timestamp = int(start_date.timestamp() * 1000)
    end_timestamp = int(end_date.timestamp() * 1000)
    
    print(f"DEBUG: Payment calculation - Period: {period_name}")
    print(f"DEBUG: Start timestamp: {start_timestamp}, End timestamp: {end_timestamp}")
    
    if creator_name.lower() in ["me", "i"]:
        creator_name = get_meegle_username_from_lark(lark_user_id)
        if not creator_name:
            return {
                "success": False,
                "error": "❌ Could not find your Meegle username. Please use your Meegle name instead."
            }
    
    creator_lookup = creator_name.lower()
    creator_user_id = CREATOR_USER_IDS.get(creator_lookup)
    
    if not creator_user_id:
        known_creators = ', '.join([k.title() for k in CREATOR_USER_IDS.keys() if not k.isdigit()])
        return {
            "success": False,
            "error": f"❌ Could not find user ID for '{creator_name}'. Known creators: {known_creators}"
        }
    
    print(f"DEBUG: Searching for creator '{creator_name}' with user_id: {creator_user_id}")
    
    try:
        result = client.search_work_items(filters=None)
        all_items = result.get("data", [])
        print(f"DEBUG: Got {len(all_items)} total work items")
        
        filtered_items = []
        for item in all_items:
            item_id = item.get('id')
            fields = item.get("fields", [])
            creator_matched = False
            
            # Check if creator matches
            for field in fields:
                if field.get("field_alias") == "content_creator":
                    creator_value = str(field.get("field_value", ""))
                    if creator_user_id == creator_value:
                        creator_matched = True
                        break
            
            if not creator_matched:
                continue
            
            # Check if Creative Production exit is in the time period
            state_times = item.get("state_times", [])
            for state in state_times:
                state_name = state.get("name", "")
                end_time = state.get("end_time", 0)
                
                if state_name == "Creative Production" and end_time > 0:
                    if start_timestamp <= end_time <= end_timestamp:
                        filtered_items.append(item)
                        print(f"DEBUG: ✅ Item {item_id} counted for payment")
                        break
        
        count = len(filtered_items)
        
        # ✅ FIXED: Get payment rate based on user's role from Lark Base
        payment_rate = get_payment_rate_for_user(creator_name, user_data)
        payment = count * payment_rate
        
        print(f"DEBUG: Final count: {count}, Rate: ${payment_rate}, Payment: ${payment}")
        
        return {
            "success": True,
            "creator": creator_name.title(),
            "period": period_name,
            "count": count,
            "payment": payment,
            "rate": payment_rate
        }
        
    except Exception as e:
        import traceback
        print(f"ERROR: Meegle API error: {e}")
        print(f"Traceback: {traceback.format_exc()}")
        return {
            "success": False,
            "error": f"❌ Error fetching creative data: {str(e)}"
        }


def count_creatives_by_language(language, time_period_str):
    client = MeegleClient()
    start_date, end_date, period_name = parse_time_period(time_period_str)
    try:
        result = client.search_work_items(filters=None)
        all_items = result.get("data", [])
        filtered_items = []
        for item in all_items:
            fields = item.get("fields", [])
            for field in fields:
                if field.get("field_alias") == "language":
                    language_value = field.get("field_value", "")
                    if language.lower() in str(language_value).lower():
                        filtered_items.append(item)
                        break
        response = f"""📊 Creative Stats by Language


Language: {language}
Period: {period_name}
Total Creatives: {len(filtered_items)}"""
        return response
    except Exception as e:
        import traceback
        print(f"ERROR: Meegle API error: {e}")
        print(f"Traceback: {traceback.format_exc()}")
        return f"❌ Error fetching creative data: {str(e)}"


def get_meegle_username_from_lark(lark_user_id):
    user_mapping = {
        "ou_18eee86dc3c6f6b223b2c434cffd9198": "alejandra",
    }
    return user_mapping.get(lark_user_id)


def get_creative_help():
    return """📊 Creative Tracker Commands


**Count creatives by creator:**
`creative count <name> <period>`
Examples:
• creative count Aure this month
• creative count Alejandra November
• creative count me October


**Creator payment:**
`creative payment <name> <period>`
Examples:
• creative payment Aure this month
• creative payment Alejandra last month
• creative payment Carolina this month


**Language breakdown:**
`creative language <language> <period>`
Examples:
• creative language Spanish this month
• creative language English November


**Time periods:**
• this month
• last month (or just "month")
• October
• November 2024


**Test API connection:**
• creative test


**Note:** Counts items that have exited the Creative Production node and moved beyond.
Payment is calculated based on user role:
• Creators: $13 per video
• Video Editors: $5.50 per video"""
