import re
from datetime import datetime
from calendar import monthrange
from meegle_api import MeegleClient

# User ID mapping for content creators
CREATOR_USER_IDS = {
    "aure": "7569613836605492757",
    "aure williams": "7569613836605492757",
    "alejandra": "7566221514945662485",
    "7562186989836045843": "7562186989836045843",
}

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

**Note:** Counts items that have exited the Creative Production node and moved beyond."""

