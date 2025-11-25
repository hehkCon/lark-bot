import re
from datetime import datetime
from calendar import monthrange
from meegle_api import MeegleClient

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
    
    # Handle "me" or "I"
    if creator_name.lower() in ["me", "i"]:
        # Map Lark user to Meegle user (you'll need to maintain this mapping)
        creator_name = get_meegle_username_from_lark(lark_user_id)
        if not creator_name:
            return f"❌ Could not find your Meegle username. Please use your Meegle name instead."
    
    # Search for user in Meegle
    user = client.search_user(creator_name)
    if not user:
        # If user search fails, try using the name directly as a filter
        print(f"DEBUG: Could not find user via search, will try direct filter")
    
    # Query work items
    filters = {
        "assignee": creator_name,  # Use name directly
        "status": "Compliance Review",  # Status after Creative Production
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat()
    }
    
    try:
        result = client.search_work_items(filters=filters)
        items = result.get("items", [])
        
        response = f"""📊 Creative Stats for {creator_name}

Period: {period_name}
Total Creatives Completed: {len(items)}

Status: Based on items that moved to "Compliance Review" status in {period_name}"""
        
        return response
        
    except Exception as e:
        print(f"ERROR: Meegle API error: {e}")
        return f"❌ Error fetching creative data: {str(e)}"

def count_creatives_by_language(language, time_period_str):
    """Count creatives by language in a time period"""
    client = MeegleClient()
    
    # Parse time period
    start_date, end_date, period_name = parse_time_period(time_period_str)
    
    # Query work items with language filter
    filters = {
        "status": "Compliance Review",
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "language": language
    }
    
    try:
        result = client.search_work_items(filters=filters)
        items = result.get("items", [])
        
        response = f"""📊 Creative Stats by Language

Language: {language}
Period: {period_name}
Total Creatives: {len(items)}"""
        
        return response
        
    except Exception as e:
        print(f"ERROR: Meegle API error: {e}")
        return f"❌ Error fetching creative data: {str(e)}"

def get_meegle_username_from_lark(lark_user_id):
    """
    Map Lark user ID to Meegle username
    You'll need to maintain this mapping - could be in a dict, database, or config file
    """
    # Example mapping - replace with your actual mapping
    user_mapping = {
        "ou_18eee86dc3c6f6b223b2c434cffd9198": "Alejandra",  # Your user ID from logs
        # Add more mappings as needed
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

**Note:** Counts are based on items that moved to "Compliance Review" status in the specified period."""
