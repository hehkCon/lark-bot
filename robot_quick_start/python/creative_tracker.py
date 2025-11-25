import re
from datetime import datetime
from calendar import monthrange
from meegle_api import MeegleClient

# User ID mapping for content creators
CREATOR_USER_IDS = {
    "aure": "7569613836605492757",
    "aure williams": "7569613836605492757",
    "alejandra": "7566221514945662485",
    # Add your user ID
    "7562186989836045843": "7562186989836045843",  # You (Alejandra based on user_key)
}

def parse_creative_command(text):
    """
    Parse commands like:
    - creative help
    - creative test
    - creative count Aure this month
    - creative stats Alejandra November
    - creative language Spanish October
    """
    text_lower = text.lower().strip()
    
    # Check if it's a creative command
    if not text_lower.startswith("creative"):
        return None
    
    parts = text.split()
    
    # Handle "creative help" (only 2 parts)
    if len(parts) == 2 and parts[1].lower() == "help":
        return {"type": "help"}
    
    # Handle "creative test" (only 2 parts)
    if len(parts) == 2 and parts[1].lower() == "test":
        return {"type": "test"}
    
    # Need at least 3 parts for other commands
    if len(parts) < 3:
        return {"error": "Invalid creative command. Type 'creative help' for usage."}
    
    command_type = parts[1].lower()  # count, stats, language
    
    if command_type in ["count", "stats"]:
        creator_name = parts[2]
        time_period = " ".join(parts[3:]) if len(parts) > 3 else "this month"
        
        return {
            "type": command_type,
            "creator": creator_name,
            "time_period": time_period
        }
    
    elif command_type == "language":
        language = parts[2]
        time_period = " ".join(parts[3:]) if len(parts) > 3 else "this month"
        
        return {
            "type": "language",
            "language": language,
            "time_period": time_period
        }
    
    return {"error": f"Unknown creative command: {command_type}. Type 'creative help' for usage."}

def parse_time_period(time_period_str):
    """
    Convert time period string to start/end dates
    Returns: (start_date, end_date, period_name)
    """
    now = datetime.now()
    time_lower = time_period_str.lower()
    
    if "this month" in time_lower:
        start_date = datetime(now.year, now.month, 1)
        last_day = monthrange(now.year, now.month)[1]
        end_date = datetime(now.year, now.month, last_day, 23, 59, 59)
        period_name = now.strftime("%B %Y")
        
    elif "last month" in time_lower:
        if now.month == 1:
            month, year = 12, now.year - 1
        else:
            month, year = now.month - 1, now.year
        start_date = datetime(year, month, 1)
        last_day = monthrange(year, month)[1]
        end_date = datetime(year, month, last_day, 23, 59, 59)
        period_name = start_date.strftime("%B %Y")
        
    else:
        # Try to parse month name (e.g., "November", "October 2024")
        month_names = {
            "january": 1, "february": 2, "march": 3, "april": 4,
            "may": 5, "june": 6, "july": 7, "august": 8,
            "september": 9, "october": 10, "november": 11, "december": 12
        }
        
        for month_name, month_num in month_names.items():
            if month_name in time_lower:
                year = now.year
                # Check if year specified
                year_match = re.search(r'20\d{2}', time_period_str)
                if year_match:
                    year = int(year_match.group())
                
                start_date = datetime(year, month_num, 1)
                last_day = monthrange(year, month_num)[1]
                end_date = datetime(year, month_num, last_day, 23, 59, 59)
                period_name = start_date.strftime("%B %Y")
                break
        else:
            # Default to this month
            start_date = datetime(now.year, now.month, 1)
            last_day = monthrange(now.year, now.month)[1]
            end_date = datetime(now.year, now.month, last_day, 23, 59, 59)
            period_name = now.strftime("%B %Y")
    
    return start_date, end_date, period_name

def count_creatives_by_creator(creator_name, time_period_str, lark_user_id=None):
    """Count creatives completed by a creator in a time period"""
    client = MeegleClient()
    
    # Parse time period
    start_date, end_date, period_name = parse_time_period(time_period_str)
    
    # Convert to milliseconds (Meegle uses epoch milliseconds)
    start_timestamp = int(start_date.timestamp() * 1000)
    end_timestamp = int(end_date.timestamp() * 1000)
    
    print(f"DEBUG: Period: {period_name}")
    print(f"DEBUG: Start timestamp: {start_timestamp} ({start_date})")
    print(f"DEBUG: End timestamp: {end_timestamp} ({end_date})")
    
    # Handle "me" or "I"
    if creator_name.lower() in ["me", "i"]:
        creator_name = get_meegle_username_from_lark(lark_user_id)
        if not creator_name:
            return f"❌ Could not find your Meegle username. Please use your Meegle name instead."
    
    # Look up user ID from name
    creator_lookup = creator_name.lower()
    creator_user_id = CREATOR_USER_IDS.get(creator_lookup)
    
    if not creator_user_id:
        return f"❌ Could not find user ID for '{creator_name}'. Known creators: {', '.join([k.title() for k in CREATOR_USER_IDS.keys() if not k.isdigit()])}"
    
    print(f"DEBUG: Searching for creator '{creator_name}' with user_id: {creator_user_id}")
    
    # Statuses that indicate creative production is complete
    valid_statuses = [
        "Compliance Review",
        "Rejected Creative - Revision",
        "Ready To Launch",
        "Creative Performance Monitoring"
    ]
    
    try:
        result = client.search_work_items(filters=None)
        
        # FIXED: data is a list directly, not a dict
        all_items = result.get("data", [])
        
        print(f"DEBUG: Got {len(all_items)} total work items")
        
        # DEBUG: Show all field aliases from first item to find completion time field
        if all_items:
            first_item_fields = all_items[0].get("fields", [])
            print(f"DEBUG: All field aliases in first item:")
            for field in first_item_fields:
                field_alias = field.get("field_alias")
                field_type = field.get("field_type_key")
                field_value = field.get("field_value")
                if "time" in field_alias.lower() or "date" in field_alias.lower() or field_type == "date":
                    print(f"  - {field_alias} ({field_type}): {field_value}")
        
        # Filter client-side by creator user ID, status, and date
        filtered_items = []
        for item in all_items:
            item_id = item.get('id')
            item_name = item.get('name')
            
            # Get current status from current_nodes
            current_nodes = item.get("current_nodes", [])
            current_status = current_nodes[0].get("name") if current_nodes else None
            
            # Look through fields for content_creator and completion time
            fields = item.get("fields", [])
            creator_matched = False
            completion_time = None
            
            for field in fields:
                field_alias = field.get("field_alias")
                
                # Check for content_creator
                if field_alias == "content_creator":
                    creator_value = str(field.get("field_value", ""))
                    if creator_user_id == creator_value:
                        creator_matched = True
                
                # Look for completion time field (adjust field_alias as needed)
                if "completion" in field_alias.lower() or "finish" in field_alias.lower():
                    completion_time = field.get("field_value")
                    print(f"DEBUG: Found completion field '{field_alias}' = {completion_time}")
            
            # If creator matched and status valid, check completion time
            if creator_matched and current_status in valid_statuses:
                if completion_time:
                    # Check if completion time is within our period
                    if start_timestamp <= completion_time <= end_timestamp:
                        filtered_items.append(item)
                        
                        # Convert timestamp to readable date
                        completion_date = datetime.fromtimestamp(completion_time / 1000)
                        print(f"DEBUG: ✅ MATCHED item {item_id}")
                        print(f"  - Name: {item_name}")
                        print(f"  - Completed on: {completion_date.strftime('%Y-%m-%d %H:%M')}")
                else:
                    print(f"DEBUG: ⚠️ Item {item_id} matched but no completion time field found")
        
        response = f"""📊 Creative Stats for {creator_name.title()}

Period: {period_name}
Total Creatives Completed: {len(filtered_items)}

Counted: Items completed during {period_name}
Statuses:
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

def count_creatives_by_language(language, time_period_str):
    """Count creatives by language in a time period"""
    client = MeegleClient()
    
    # Parse time period
    start_date, end_date, period_name = parse_time_period(time_period_str)
    
    try:
        result = client.search_work_items(filters=None)
        
        # FIXED: data is a list directly, not a dict
        all_items = result.get("data", [])
        
        # Filter client-side by language
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
    """
    Map Lark user ID to Meegle username
    """
    # Map to Meegle creator name (which will then be looked up in CREATOR_USER_IDS)
    user_mapping = {
        "ou_18eee86dc3c6f6b223b2c434cffd9198": "alejandra",
        # Add more Lark to Meegle mappings as needed
    }
    
    return user_mapping.get(lark_user_id)

def get_creative_help():
    """Return help message for creative commands"""
    return """📊 Creative Tracker Commands

**Count creatives by creator:**
`creative count <name> <period>`
Examples:
• creative count Aure this month
• creative count Alejandra November
• creative count me October

**Language breakdown:**
`creative language <language> <period>`
Examples:
• creative language Spanish this month
• creative language English November

**Time periods:**
• this month
• last month
• October
• November 2024

**Test API connection:**
• creative test

**Note:** Counts items that have completed Creative Production (in Compliance Review, Rejected Creative - Revision, Ready To Launch, or Creative Performance Monitoring)."""

