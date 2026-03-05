# creative_tracker.py - CREATOR + EDITOR ROLES (SEPARATE FETCH), DUAL WORKSPACE, CONTENT TYPE PAYMENTS

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
    "harry": "7562186989836045843",
    "carolina": "7581455452412628499",
    "april": "7599935172070493716",
    "blessing": "7599871694760644116",
    "janett": "7600049949983788564",
    "guillermo": "7600059664037973526",
    "lakshmi": "7599918880215076372",
    "giovani": "7600196845523963414",
    "valentina": "7601310531932261909",
    "april": "7599935172070493716",
    "juliette": "7604758218060877334",
    "eduardo":	"7602243156662308374",
    "octokani":	"7602308678007393814",
    "nicole": "7605694135588163094"
}

# Workspace configs
WORKSPACES = [
    {
        "project_key": "68fef3aea7d53233b3285b15",
        "type_key": "story",
        "name": "SearchArb",
        "content_type_field": "media_type",
        "payment_rates": {
            "ugc video": 13.50,
            "video editor": 5.50,
            "lead gen": 35.00,
        }
    },
    {
        "project_key": "69730343e177229598681c13",
        "type_key": "story",
        "name": "External",
        "content_type_field": "content_type",
        "payment_rates": {
            "ugc": 35.00,
            "external - search arb": 13.50,
            "external - editor": 11.00,
            "lead gen": 35.00,
        }
    }
]

# Role IDs (same in both workspaces)
CREATOR_ROLE_ID = "role_9e1a72"
EDITOR_ROLE_ID = "role_0be9df"

# Editor role payment rate
EDITOR_ROLE_RATE = 11.00

DEFAULT_PAYMENT_RATE = 13.50


def get_payment_rate_from_item(item, workspace_config):
    """Read content_type or media_type label from item and return matching rate."""
    field_alias = workspace_config["content_type_field"]
    payment_rates = workspace_config["payment_rates"]

    fields = item.get("fields", [])
    for field in fields:
        if field.get("field_alias") == field_alias:
            field_value = field.get("field_value", "")
            label = ""
            if isinstance(field_value, dict):
                label = field_value.get("label", "").lower().strip()
            elif isinstance(field_value, list) and len(field_value) > 0:
                label = field_value[0].get("label", "").lower().strip()
            elif isinstance(field_value, str):
                label = field_value.lower().strip()

            rate = payment_rates.get(label, DEFAULT_PAYMENT_RATE)
            print(f"DEBUG: {field_alias} label='{label}' → rate=${rate}")
            return rate, label

    print(f"DEBUG: No {field_alias} field found on item, using default ${DEFAULT_PAYMENT_RATE}")
    return DEFAULT_PAYMENT_RATE, "unknown"


def fetch_items_by_role(client, user_id, role_id, workspace, start_timestamp, end_timestamp):
    """
    Fetch ALL work items where user has given role_id in role_owners,
    and exited Creative Production within the time period.
    Works for both creator role and editor role.
    """
    try:
        result = client.search_work_items(filters={
            "project_key": workspace["project_key"],
            "type_key": workspace["type_key"]
        })
        all_items = result.get("data", [])
        print(f"DEBUG: [{workspace['name']}] role={role_id} - Got {len(all_items)} total items")

        matched = []
        for item in all_items:
            item_id = item.get("id")
            fields = item.get("fields", [])
            role_matched = False

            for field in fields:
                if field.get("field_key") == "role_owners":
                    role_entries = field.get("field_value", [])
                    for entry in role_entries:
                        if entry.get("role") == role_id:
                            owners = entry.get("owners") or []
                            if user_id in [str(o) for o in owners]:
                                role_matched = True
                                break
                    break

            if not role_matched:
                continue

            # Check if Creative Production exit is in the time period
            state_times = item.get("state_times", [])
            for state in state_times:
                if state.get("name") == "Creative Production" and state.get("end_time", 0) > 0:
                    end_time = state["end_time"]
                    if start_timestamp <= end_time <= end_timestamp:
                        matched.append(item)
                        completion_date = datetime.fromtimestamp(end_time / 1000)
                        print(f"DEBUG: [{workspace['name']}] ✅ role={role_id} Item {item_id} counted - exited at {completion_date}")
                        break
                    else:
                        print(f"DEBUG: [{workspace['name']}] role={role_id} Item {item_id} - exit out of period")

        print(f"DEBUG: [{workspace['name']}] role={role_id} - {len(matched)} items matched for user {user_id}")
        return matched

    except Exception as e:
        import traceback
        print(f"ERROR fetching [{workspace['name']}] role={role_id}: {e}\n{traceback.format_exc()}")
        return []


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
    elif "last month" in time_lower or ("month" in time_lower and "this" not in time_lower):
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
    """Returns formatted response with creative count across both workspaces"""
    client = MeegleClient()
    start_date, end_date, period_name = parse_time_period(time_period_str)
    start_timestamp = int(start_date.timestamp() * 1000)
    end_timestamp = int(end_date.timestamp() * 1000)

    if creator_name.lower() in ["me", "i"]:
        creator_name = get_meegle_username_from_lark(lark_user_id)
        if not creator_name:
            return "❌ Could not find your Meegle username. Please use your Meegle name instead."

    creator_lookup = creator_name.lower()
    creator_user_id = CREATOR_USER_IDS.get(creator_lookup)
    if not creator_user_id:
        known = ', '.join([k.title() for k in CREATOR_USER_IDS.keys() if len(k) > 3])
        return f"❌ Could not find user ID for '{creator_name}'. Known creators: {known}"

    workspace_counts = {}
    total = 0
    for workspace in WORKSPACES:
        items = fetch_items_by_role(client, creator_user_id, CREATOR_ROLE_ID, workspace, start_timestamp, end_timestamp)
        workspace_counts[workspace["name"]] = len(items)
        total += len(items)

    breakdown = "\n".join([f"• {name}: {count}" for name, count in workspace_counts.items() if count > 0])
    if not breakdown:
        breakdown = "• No creatives found in either workspace"

    response = f"""📊 Creative Stats for {creator_name.title()}

Period: {period_name}
Total Creatives Completed: {total}

{breakdown}

Counted: Items that exited Creative Production during {period_name}"""
    return response


def get_creator_count_and_payment(creator_name, time_period_str, user_data=None, lark_user_id=None):
    """
    Returns dict with:
    - Creator items (role_9e1a72) + content type payment
    - Editor items (role_0be9df) fetched separately + $11 each
    Both tracked per workspace.
    """
    client = MeegleClient()
    start_date, end_date, period_name = parse_time_period(time_period_str)
    start_timestamp = int(start_date.timestamp() * 1000)
    end_timestamp = int(end_date.timestamp() * 1000)

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
        known = ', '.join([k.title() for k in CREATOR_USER_IDS.keys() if len(k) > 3])
        return {
            "success": False,
            "error": f"❌ Could not find user ID for '{creator_name}'. Known creators: {known}"
        }

    total_payment = 0.0
    total_creator_count = 0
    total_editor_count = 0
    workspace_breakdown = {}

    for workspace in WORKSPACES:
        # ── CREATOR ITEMS ──────────────────────────────────────
        creator_items = fetch_items_by_role(
            client, creator_user_id, CREATOR_ROLE_ID,
            workspace, start_timestamp, end_timestamp
        )

        type_breakdown = {}
        creator_payment = 0.0
        for item in creator_items:
            rate, label = get_payment_rate_from_item(item, workspace)
            creator_payment += rate
            if label not in type_breakdown:
                type_breakdown[label] = {"count": 0, "payment": 0.0}
            type_breakdown[label]["count"] += 1
            type_breakdown[label]["payment"] += rate

        # ── EDITOR ITEMS (separate fetch) ──────────────────────
        editor_items = fetch_items_by_role(
            client, creator_user_id, EDITOR_ROLE_ID,
            workspace, start_timestamp, end_timestamp
        )
        editor_count = len(editor_items)
        editor_payment = editor_count * EDITOR_ROLE_RATE

        # Only add workspace if there's something to show
        if creator_items or editor_items:
            workspace_breakdown[workspace["name"]] = {
                "creator_count": len(creator_items),
                "creator_payment": creator_payment,
                "editor_count": editor_count,
                "editor_payment": editor_payment,
                "types": type_breakdown
            }

        total_creator_count += len(creator_items)
        total_editor_count += editor_count
        total_payment += creator_payment + editor_payment

    print(f"DEBUG: Total creator={total_creator_count}, editor={total_editor_count}, payment=${total_payment}")

    return {
        "success": True,
        "creator": creator_name.title(),
        "period": period_name,
        "count": total_creator_count,
        "editor_count": total_editor_count,
        "payment": total_payment,
        "workspace_breakdown": workspace_breakdown
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
        print(f"ERROR: {e}\n{traceback.format_exc()}")
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
• creative count Lakshmi this month

**Creator payment:**
`creative payment <name> <period>`
Examples:
• creative payment Aure this month
• creative payment Lakshmi last month
• creative payment Carolina this month

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

**Note:** Counts items that exited Creative Production across both workspaces.

SearchArb rates (media_type):
• UGC Video: $13.50 | Video Editor: $5.50 | Lead Gen: $35.00

External rates (content_type):
• UGC: $35.00 | Lead Gen: $35.00
• External - Search Arb: $13.50 | External - Editor: $11.00

Editor role: $11.00 per item (tracked separately from creator role)"""
