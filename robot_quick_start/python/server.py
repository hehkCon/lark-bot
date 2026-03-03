# ✅ server.py - UPDATED: SEPARATE CREATOR + EDITOR ROLE PAYMENTS

import json
import logging
import os
import threading
import time  
from flask import Flask, jsonify, request
from api import MessageApiClient, TokenManager
from lark_base_client import LarkBaseClient, PerformanceTracker
from performance_commands import PerformanceCommands
from commission import calculate_commission, get_help_message
from creative_tracker import (
    parse_creative_command,
    count_creatives_by_creator,
    get_creator_count_and_payment,
    count_creatives_by_language,
    get_creative_help
)

# ✅ SCHEDULERS
from performance_scheduler import PerformanceScheduler
from user_performance_scheduler import UserPerformanceScheduler


# Load environment variables
APP_ID = os.getenv("APP_ID")
APP_SECRET = os.getenv("APP_SECRET")
VERIFICATION_TOKEN = os.getenv("VERIFICATION_TOKEN", "")
LARK_HOST = os.getenv("LARK_HOST", "https://open.larksuite.com")
LARK_BASE_APP_TOKEN = os.getenv("LARK_BASE_APP_TOKEN")
LARK_BASE_COMBINED_PERFORMANCE_TABLE_ID = os.getenv("LARK_BASE_COMBINED_PERFORMANCE_TABLE_ID")
LARK_BASE_USER_INFO_TABLE_ID = os.getenv("LARK_BASE_USER_INFO_TABLE_ID")

# Configurable settings
PORT = int(os.getenv("PORT", 10000))
DEBUG = os.getenv("DEBUG", "False").lower() == "true"

# Debug prints
print(f"DEBUG: APP_ID={APP_ID}")
print(f"DEBUG: APP_SECRET={'SET' if APP_SECRET else 'NOT SET'}")
print(f"DEBUG: LARK_HOST={LARK_HOST}")
print(f"DEBUG: LARK_BASE_APP_TOKEN={'SET' if LARK_BASE_APP_TOKEN else 'MISSING'}")
print(f"DEBUG: LARK_BASE_USER_INFO_TABLE_ID={LARK_BASE_USER_INFO_TABLE_ID}")
print(f"DEBUG: LARK_BASE_COMBINED_PERFORMANCE_TABLE_ID={LARK_BASE_COMBINED_PERFORMANCE_TABLE_ID}")
print(f"DEBUG: PORT={PORT}, DEBUG={DEBUG}")


app = Flask(__name__)


# Initialize message client and token manager (GLOBAL)
token_manager = TokenManager(APP_ID, APP_SECRET, LARK_HOST)
message_api_client = MessageApiClient(APP_ID, APP_SECRET, token_manager)


# GLOBAL SINGLETONS
performance_tracker_instance = None
user_data_cache = None
performance_scheduler_instance = None
user_performance_scheduler_instance = None


# Thread-safe duplicate event processing
processed_events = set()
processed_events_lock = threading.Lock()


@app.errorhandler(Exception)
def handle_exception(e):
    logging.error(f"Unhandled exception: {e}", exc_info=True)
    return jsonify({"error": str(e)}), 500


def init_trackers():
    """Initialize performance tracker ONCE at startup"""
    global performance_tracker_instance, user_data_cache
    global performance_scheduler_instance, user_performance_scheduler_instance

    try:
        lark_client = LarkBaseClient(
            app_token=LARK_BASE_APP_TOKEN,
            table_id=LARK_BASE_USER_INFO_TABLE_ID,
            performance_table_id=LARK_BASE_COMBINED_PERFORMANCE_TABLE_ID,
            token_manager=token_manager
        )
        performance_tracker_instance = PerformanceTracker(lark_client=lark_client)

        user_data_cache = {
            "data": None,
            "expiry": 0,
            "ttl": 300  # 5 minutes
        }

        print("✅ DEBUG: Performance tracker & user cache initialized at startup")
        print("✅ DEBUG: Token manager integrated - no more stale tokens!")
        print(f"✅ DEBUG: Using combined performance table: {LARK_BASE_COMBINED_PERFORMANCE_TABLE_ID}")

        init_schedulers()

    except Exception as e:
        print(f"❌ ERROR: Failed to initialize trackers: {e}")
        performance_tracker_instance = None


def init_schedulers():
    """Initialize and start performance schedulers"""
    global performance_scheduler_instance, user_performance_scheduler_instance

    try:
        if performance_tracker_instance is None:
            print("⚠️ WARNING: Cannot initialize schedulers - performance_tracker_instance is None")
            return

        team_chat_mapping = {
            "Dioulde's team": "oc_fdb7932f2822ba72af2097415bd9950f",
            "Kath's team": "oc_adf04e6adc2205c661e177354abad176",
            "Amanda's team": "oc_2baefe6e05e47f00b376c33e5d938101",
            "Jello's team": "oc_b017b223e054e80c14b5957bc77f8467"
        }

        performance_scheduler_instance = PerformanceScheduler(
            message_api_client=message_api_client,
            performance_tracker=performance_tracker_instance,
            team_chat_mapping=team_chat_mapping,
            timezone="America/Toronto"
        )
        performance_scheduler_instance.start()
        print("✅ DEBUG: Team performance scheduler started (9:10 AM EST)")

        user_performance_scheduler_instance = UserPerformanceScheduler(
            message_api_client=message_api_client,
            performance_tracker=performance_tracker_instance,
            timezone="America/Toronto"
        )
        user_performance_scheduler_instance.start()
        print("✅ DEBUG: User performance scheduler started (9:50 AM EST)")

    except Exception as e:
        print(f"❌ ERROR: Failed to initialize schedulers: {e}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")


@app.route("/", methods=["GET", "POST"])
def callback_event_handler():
    if request.method == "GET":
        return jsonify({"message": "Bot is running"}), 200

    req_data = request.get_json()
    print(f"DEBUG: Received POST data: {json.dumps(req_data, indent=2)}")

    # URL verification challenge
    if req_data.get("type") == "url_verification":
        challenge = req_data.get("challenge")
        print(f"DEBUG: URL verification challenge received")
        return jsonify({"challenge": challenge})

    # Thread-safe duplicate event check
    event_id = req_data.get("header", {}).get("event_id")
    with processed_events_lock:
        if event_id in processed_events:
            print(f"DEBUG: Duplicate event {event_id} - ignoring")
            return jsonify({"message": "duplicate"}), 200
        processed_events.add(event_id)
        if len(processed_events) > 1000:
            processed_events.clear()
            print("DEBUG: Cleared processed_events cache")

    print(f"DEBUG: Processing new event {event_id}")

    event_type = req_data.get("header", {}).get("event_type")
    print(f"DEBUG: Event type: {event_type}")

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

        # Strip @mention prefix in group chats
        if chat_type == "group" and text.startswith("@"):
            text = text.split(" ", 1)[1] if " " in text else ""
            print(f"DEBUG: Stripped mention, cleaned text: {text}")

        logging.info(f"Received message from {user_open_id} in {chat_type} chat: {text}")
        print(f"DEBUG: Message from {user_open_id} in {chat_type} (chat_id: {chat_id}): {text}")

        response_text = None
        text_lower = text.lower()

        if performance_tracker_instance is None:
            print("⚠️ WARNING: Performance tracker not initialized")
            response_text = "❌ Bot services not ready. Please wait 30 seconds and try again."
        else:
            # ── PERF HELP ──────────────────────────────────────────
            if text_lower == "perf help":
                try:
                    current_time = time.time()
                    if not user_data_cache["data"] or current_time > user_data_cache["expiry"]:
                        print("DEBUG: Refreshing user data cache")
                        user_data_cache["data"] = performance_tracker_instance.client.get_user_data_dict()
                        user_data_cache["expiry"] = current_time + user_data_cache["ttl"]
                    user_data = user_data_cache["data"]
                    help_handler = PerformanceCommands(performance_tracker_instance, user_data)
                    response_text = help_handler._get_help_text()
                except Exception as e:
                    response_text = f"❌ Error fetching help: {str(e)}"
                    print(f"DEBUG: Error in perf help: {e}")

            # ── PERF COMMANDS ──────────────────────────────────────
            elif text_lower.startswith("perf"):
                try:
                    current_time = time.time()
                    if not user_data_cache["data"] or current_time > user_data_cache["expiry"]:
                        print("DEBUG: Refreshing user data cache")
                        user_data_cache["data"] = performance_tracker_instance.client.get_user_data_dict()
                        user_data_cache["expiry"] = current_time + user_data_cache["ttl"]
                    user_data = user_data_cache["data"]
                    performance_commands_handler = PerformanceCommands(performance_tracker_instance, user_data)
                    response_text = performance_commands_handler.handle_performance_command(text, user_open_id)
                except Exception as e:
                    response_text = f"❌ Error fetching performance data: {str(e)}"
                    print(f"DEBUG: Error in perf command: {e}")

            # ── COMMISSION HELP ────────────────────────────────────
            elif text_lower == "commission help":
                response_text = get_help_message()

            # ── COMMISSION COMMANDS ────────────────────────────────
            elif any(text.upper().startswith(p) for p in ["GINSU", "BING", "YAHOO", "RSOC"]):
                response_text = calculate_commission(text, user_open_id)

            # ── CREATIVE COMMANDS ──────────────────────────────────
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

                elif parsed["type"] == "payment":
                    try:
                        result = get_creator_count_and_payment(
                            parsed["creator"],
                            parsed["time_period"],
                            lark_user_id=user_open_id
                        )
                        if result["success"]:
                            breakdown_lines = []
                            for ws_name, ws_data in result.get("workspace_breakdown", {}).items():
                                creator_count = ws_data.get("creator_count", 0)
                                editor_count = ws_data.get("editor_count", 0)
                                breakdown_lines.append(f"\n📁 {ws_name} ({creator_count} videos as creator)")

                                # Content type breakdown
                                for label, type_data in ws_data.get("types", {}).items():
                                    breakdown_lines.append(
                                        f"  • {label.title()} x{type_data['count']} = ${type_data['payment']:.2f}"
                                    )

                                # Editor role breakdown (separate)
                                if editor_count > 0:
                                    breakdown_lines.append(f"  Video Editor role: {editor_count} items")
                                    breakdown_lines.append(
                                        f"  • Video Editor x{editor_count} = ${ws_data['editor_payment']:.2f}"
                                    )

                                ws_total = ws_data["creator_payment"] + ws_data["editor_payment"]
                                breakdown_lines.append(f"  Subtotal: ${ws_total:.2f}")

                            breakdown_text = "\n".join(breakdown_lines) if breakdown_lines else "\n• No creatives found"
                            editor_summary = (
                                f"\nTotal Editor Roles: {result['editor_count']}"
                                if result.get("editor_count", 0) > 0 else ""
                            )

                            response_text = (
                                f"💰 Creative Payment — {result['creator']} ({result['period']})\n"
                                f"\nTotal Videos: {result['count']} (as creator)"
                                f"{editor_summary}"
                                f"{breakdown_text}\n"
                                f"\n━━━━━━━━━━━━━━━━"
                                f"\n💵 Total Payment: ${result['payment']:.2f}"
                            )
                        else:
                            response_text = result["error"]
                    except Exception as e:
                        import traceback
                        print(f"DEBUG: Error in creative payment: {e}")
                        print(traceback.format_exc())
                        response_text = f"❌ Error calculating payment: {str(e)}"

                elif parsed["type"] == "language":
                    response_text = count_creatives_by_language(
                        parsed["language"], parsed["time_period"]
                    )
                else:
                    response_text = "❌ Unknown creative command"

            # ── FALLBACK ───────────────────────────────────────────
            else:
                response_text = """👋 **Hello!**

I'm your Intentt Bot Assistant. Here's what I can do:

**💰 Commission Calculator**
• `Ginsu 5000 4000` - Calculate commission
• `RSOC $3,000 $2,500` - Works with $ and commas!
• `help` - See all commands

**🎨 Creative Tracker**
• `creative count Alejandra this month` - Track creatives
• `creative help` - See all commands

**📈 Performance Tracker**
• `perf me` - Your performance
• `perf team` - All teams
• `perf amanda` - Amanda's Team
• `perf help` - See all commands
- Please note that data is manually updated 
  into a Lark Base table and can be delayed

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
                print("✅ DEBUG: Successfully sent response")
            except Exception as e:
                logging.error(f"Failed to send message: {e}")
                print(f"❌ DEBUG: Failed to send message: {e}")
                return jsonify({"error": str(e)}), 500

        return jsonify({"message": "success"}), 200

    logging.warning(f"Unknown event type: {event_type}")
    print(f"DEBUG: Full request for unknown event: {json.dumps(req_data, indent=2)}")
    return jsonify({"message": "unknown event"}), 200


@app.route("/healthcheck", methods=["GET"])
def healthcheck():
    """Health check - forces tracker initialization"""
    init_trackers()
    return jsonify({
        "status": "healthy",
        "performance_tracker": performance_tracker_instance is not None,
        "performance_scheduler": performance_scheduler_instance is not None,
        "user_scheduler": user_performance_scheduler_instance is not None,
        "message_client": message_api_client is not None,
        "token_manager": token_manager.token is not None
    })


@app.route("/meegle-webhook", methods=["POST"])
def meegle_webhook_handler():
    """Handle Meegle webhook events (placeholder)"""
    print("DEBUG: Received Meegle webhook")
    return jsonify({"message": "received"}), 200


def shutdown_schedulers():
    """Gracefully stop schedulers on shutdown"""
    global performance_scheduler_instance, user_performance_scheduler_instance
    if performance_scheduler_instance:
        performance_scheduler_instance.stop()
        print("DEBUG: Team performance scheduler stopped")
    if user_performance_scheduler_instance:
        user_performance_scheduler_instance.stop()
        print("DEBUG: User performance scheduler stopped")


# Initialize at startup
with app.app_context():
    init_trackers()

if __name__ == "__main__":
    try:
        app.run(host="0.0.0.0", port=PORT, debug=DEBUG)
    except KeyboardInterrupt:
        print("\nShutting down...")
        shutdown_schedulers()
