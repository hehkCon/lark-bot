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
        creator_name = get_meegle_username_from_lark(lark_user_id)
        if not creator_name:
            return f"❌ Could not find your Meegle username. Please use your Meegle name instead."
    
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
        print(f"DEBUG: Looking for creator: {creator_name}")
        print(f"DEBUG: Valid statuses: {valid_statuses}")
        
        # Filter client-side by creator name and status
        filtered_items = []
        for item in all_items:
            item_id = item.get('id')
            item_name = item.get('name')
            
            # Get current status from current_nodes
            current_nodes = item.get("current_nodes", [])
            current_status = current_nodes[0].get("name") if current_nodes else None
            
            # DEBUG: Print first item's fields to see structure
            if item_id == all_items[0].get('id'):
                print(f"DEBUG: First item structure:")
                print(f"  - current_status: {current_status}")
                fields = item.get("fields", [])
                for field in fields[:5]:  # Show first 5 fields
                    print(f"  - field_alias: {field.get('field_alias')}, field_value: {field.get('field_value')}")
            
            # Look through fields for content_creator
            fields = item.get("fields", [])
            creator_matched = False
            
            for field in fields:
                if field.get("field_alias") == "content_creator":
                    creator_value = field.get("field_value", "")
                    
                    # Only log for first few items to avoid spam
                    if len(filtered_items) < 3:
                        print(f"DEBUG: Item {item_id} - Found content_creator field")
                        print(f"DEBUG: creator_value type: {type(creator_value)}")
                        print(f"DEBUG: creator_value: {creator_value}")
                    
                    # Handle different value types
                    if isinstance(creator_value, dict):
                        # Might be {"label": "Aure Williams", "value": "..."}
                        creator_text = creator_value.get("label", "") or creator_value.get("name", "")
                    elif isinstance(creator_value, list):
                        # Might be a list of users
                        creator_text = " ".join([str(u.get("label", "") or u.get("name", "")) if isinstance(u, dict) else str(u) for u in creator_value])
                    else:
                        creator_text = str(creator_value)
                    
                    if creator_name.lower() in creator_text.lower():
                        creator_matched = True
                        
                        # Now check if status is valid
                        if current_status in valid_statuses:
                            filtered_items.append(item)
                            print(f"DEBUG: ✅ MATCHED item {item_id} - creator: {creator_text}, status: {current_status}")
                        else:
                            print(f"DEBUG: ⚠️ Creator matched but wrong status - item {item_id}, status: {current_status}")
                        break
            
            if not creator_matched and len(filtered_items) < 3:
                print(f"DEBUG: ❌ No creator match for item {item_id}")
        
        response = f"""📊 Creative Stats for {creator_name}

Period: {period_name}
Total Creatives Completed: {len(filtered_items)}

Counted statuses:
• Compliance Review
• Rejected Creative - Revision
• Ready To Launch
• Creative Performance Monitoring

Note: Date filtering coming soon"""
        
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

**Note:** Counts items that have completed Creative Production (in Compliance Review, Rejected Creative - Revision, Ready To Launch, or Creative Performance Monitoring)."""

