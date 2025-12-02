import json
import logging
import os
from flask import Flask, jsonify, request
from api import MessageApiClient, TokenManager
from lark_base_client import PerformanceTracker
from performance_commands import PerformanceCommands
from commission import calculate_commission, get_help_message
from creative_tracker import parse_creative_command, count_creatives_by_creator, count_creatives_by_language, get_creative_help


# Load environment variables
APP_ID = os.getenv("APP_ID")
APP_SECRET = os.getenv("APP_SECRET")
VERIFICATION_TOKEN = os.getenv("VERIFICATION_TOKEN", "")
LARK_HOST = os.getenv("LARK_HOST", "https://open.larksuite.com")


LARK_BASE_APP_TOKEN = os.getenv("LARK_BASE_APP_TOKEN")
LARK_BASE_PERFORMANCE_TABLE_ID = os.getenv("LARK_BASE_PERFORMANCE_TABLE_ID")
LARK_BASE_PROJECTIONS_TABLE_ID = os.getenv("LARK_BASE_PROJECTIONS_TABLE_ID")
LARK_BASE_USER_INFO_TABLE_ID = os.getenv("LARK_BASE_USER_INFO_TABLE_ID")


# Debug prints
print(f"DEBUG: APP_ID={APP_ID}")
print(f"DEBUG: APP_SECRET={'SET' if APP_SECRET else 'NOT SET'}")
print(f"DEBUG: LARK_HOST={LARK_HOST}")
print(f"DEBUG: LARK_BASE_APP_TOKEN={'SET' if LARK_BASE_APP_TOKEN else 'MISSING'}")
print(f"DEBUG: LARK_BASE_USER_INFO_TABLE_ID={LARK_BASE_USER_INFO_TABLE_ID}")


app = Flask(__name__)


# Initialize message client and token manager
token_manager = TokenManager(APP_ID, APP_SECRET, LARK_HOST)
message_api_client = MessageApiClient(APP_ID, APP_SECRET, token_manager)


# Track processed events to prevent duplicates
processed_events = set()


@app.errorhandler(Exception)
def handle_exception(e):
    logging.error(f"Unhandled exception: {e}", exc_info=True)
    return jsonify({"error": str(e)}), 500


@app.route("/", methods=["GET", "POST"])
def callback_event_handler():
    if request.method == "GET":
        return jsonify({"message": "Bot is running"}), 200


    # POST request - handle Lark events
    req_data = request.get_json()
    print(f"DEBUG: Received POST data: {json.dumps(req_data, indent=2)}")


    # URL verification challenge
    if req_data.get("type") == "url_verification":
        challenge = req_data.get("challenge")
        print(f"DEBUG: URL verification challenge received")
        return jsonify({"challenge": challenge})


    # Extract event ID and check for duplicates
    event_id = req_data.get("header", {}).get("event_id")
    global processed_events
    if event_id in processed_events:
        print(f"DEBUG: Duplicate event {event_id} - ignoring (already processed)")
        return jsonify({"message": "duplicate"}), 200


    processed_events.add(event_id)
    if len(processed_events) > 1000:
        processed_events.clear()


    print(f"DEBUG: Processing new event {event_id}")


    # Extract event type
    event_type = req_data.get("header", {}).get("event_type")
    print(f"DEBUG: Event type: {event_type}")


    # Message received event
    if event_type == "im.message.receive_v1":
        event_data = req_data.get("event", {})
        message = event_data.get("message", {})
        message_type = message.get("message_type")
        print(f"DEBUG: Message type: {message_type}")


        if message_type != "text":
            logging.info(f"Ignoring non-text message type: {message_type}")
            return jsonify({"message": "ignored"}), 200


        content_str = message.get("content", "{}")
        content = json.loads(content_str)
        text = content.get("text", "").strip()


        sender = event_data.get("sender", {})
        sender_id = sender.get("sender_id", {})
        user_open_id = sender_id.get("open_id")


        chat_id = message.get("chat_id")
        chat_type = message.get("chat_type")


        if chat_type == "group" and text.startswith("@"):
            text = text.split(" ", 1)[1] if " " in text else ""
            print(f"DEBUG: Stripped mention prefix, cleaned text: {text}")


        logging.info(f"Received message from {user_open_id} in {chat_type} chat: {text}")
        print(f"DEBUG: Received message from {user_open_id} in {chat_type} chat (chat_id: {chat_id}): {text}")


        response_text = None
        text_lower = text.lower()


        # Handle perf help explicitly
        if text_lower == "perf help":
            try:
                performance_tracker = PerformanceTracker(
                    app_token=LARK_BASE_APP_TOKEN,
                    performance_table_id=LARK_BASE_PERFORMANCE_TABLE_ID,
                    projections_table_id=LARK_BASE_PROJECTIONS_TABLE_ID,
                    user_info_table_id=LARK_BASE_USER_INFO_TABLE_ID,  # ✅ ADDED
                    tenant_access_token=token_manager.get_token(),
                    host=LARK_HOST
                )
                help_handler = PerformanceCommands(performance_tracker, performance_tracker.get_user_data())
                response_text = help_handler._get_help_text()
            except Exception as e:
                response_text = f"❌ Error fetching help: {str(e)}"


        # Handle performance commands
        elif text_lower.startswith("perf"):
            try:
                performance_tracker = PerformanceTracker(
                    app_token=LARK_BASE_APP_TOKEN,
                    performance_table_id=LARK_BASE_PERFORMANCE_TABLE_ID,
                    projections_table_id=LARK_BASE_PROJECTIONS_TABLE_ID,
                    user_info_table_id=LARK_BASE_USER_INFO_TABLE_ID,  # ✅ ADDED
                    tenant_access_token=token_manager.get_token(),
                    host=LARK_HOST
                )
                user_data = performance_tracker.get_user_data()
                performance_commands_handler = PerformanceCommands(performance_tracker, user_data)
                response_text = performance_commands_handler.handle_performance_command(text, user_open_id)
            except Exception as e:
                response_text = f"❌ Error fetching performance data: {str(e)}"


        # Handle commission help explicitly
        elif text_lower == "commission help":
            response_text = get_help_message()


        # Handle commission commands
        elif any(text.upper().startswith(platform) for platform in ["GINSU", "BING", "YAHOO", "RSOC"]):
            response_text = calculate_commission(text, user_open_id)


        # Handle creative commands
        elif text_lower.startswith("creative"):
            parsed = parse_creative_command(text)
            if parsed is None:
                response_text = "❌ Invalid creative command. Type 'creative help' for usage."
            elif "error" in parsed:
                response_text = parsed["error"]
            elif parsed.get("type") == "help":
                response_text = get_creative_help()
            elif parsed.get("type") == "test":
                try:
                    from meegle_api import MeegleClient
                    client = MeegleClient()
                    result = client.test_connection()
                    items = result.get("data", [])
                    item_count = len(items)
                    first_item = items[0] if items else None
                    item_name = first_item.get("name", "N/A") if first_item else "No items"
                    item_id = first_item.get("id", "N/A") if first_item else "N/A"
                    response_text = (
                        f"✅ Meegle API Connected!\n"
                        f"Items retrieved: {item_count}\n"
                        f"Response keys: {list(result.keys())}\n"
                        f"First item:\n- ID: {item_id}\n- Name: {item_name}\n"
                        "Full response structure working!"
                    )
                except Exception as e:
                    import traceback
                    response_text = f"❌ Meegle API test failed: {str(e)}\n\nTraceback:\n{traceback.format_exc()}"
            elif parsed["type"] in ["count", "stats"]:
                response_text = count_creatives_by_creator(
                    parsed["creator"], parsed["time_period"], lark_user_id=user_open_id
                )
            elif parsed["type"] == "language":
                response_text = count_creatives_by_language(parsed["language"], parsed["time_period"])
            else:
                response_text = "❌ Unknown creative command"


        # Unknown command fallback
        else:
            response_text = """👋 **Hello!**

I'm your BASE Media Buying Bot. Here's what I can do:

**💰 Commission Calculator**
• `Ginsu 5000 4000` - Calculate commission
• `RSOC $3,000 $2,500` - Works with $ and commas!

**📊 Creative Tracker**
• `creative count Alejandra this month` - Track creatives
• `creative help` - See all commands

**📈 Performance Tracker**
• `perf me` - Your performance
• `perf team` - All teams
• `perf amanda` - Amanda's Team
• `perf help` - See all commands

Type any command to get started! 🚀"""


        # Send response
        if response_text:
            try:
                if chat_type == "group":
                    print(f"DEBUG: Sending to group chat {chat_id}")
                    message_api_client.send_text_with_chat_id(chat_id, response_text)
                else:
                    print(f"DEBUG: Sending to user {user_open_id}")
                    message_api_client.send_text_with_open_id(user_open_id, response_text)
                logging.info(f"Sent response to {chat_type} chat")
                print("DEBUG: Successfully sent response")
            except Exception as e:
                logging.error(f"Failed to send message: {e}")
                print(f"DEBUG: Failed to send message: {e}")
                return jsonify({"error": str(e)}), 500


        return jsonify({"message": "success"}), 200


    # Unknown event type
    logging.warning(f"Unknown event type: {event_type}")
    print(f"DEBUG: Full request data for unknown event: {json.dumps(req_data, indent=2)}")
    return jsonify({"message": "unknown event"}), 200



@app.route("/meegle-webhook", methods=["POST"])
def meegle_webhook_handler():
    """Handle Meegle webhook events (placeholder for future use)"""
    print("DEBUG: Received Meegle webhook")
    return jsonify({"message": "received"}), 200



if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)

