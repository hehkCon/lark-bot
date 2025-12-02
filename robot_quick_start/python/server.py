import os
from flask import Flask, request, jsonify
from dotenv import load_dotenv
import json
from api import MessageApiClient, TokenManager
from lark_base_client import PerformanceTracker
from performance_commands import PerformanceCommands
from commission import calculate_commission
from creative_tracker import parse_creative_command, count_creatives_by_creator, count_creatives_by_language, get_creative_help


# Load environment variables
load_dotenv()


# Initialize Flask app
app = Flask(__name__)


# Initialize API clients
token_manager = TokenManager(
    app_id=os.getenv("APP_ID"),
    app_secret=os.getenv("APP_SECRET"),
    host=os.getenv("LARK_HOST", "https://open.larksuite.com")
)


message_api_client = MessageApiClient(
    app_id=os.getenv("APP_ID"),
    app_secret=os.getenv("APP_SECRET"),
    token_manager=token_manager
)


# Performance schedulers disabled for debugging
performance_scheduler = None
print("DEBUG: Performance scheduler disabled for testing")

user_performance_scheduler = None
print("DEBUG: User performance scheduler disabled for testing")


def callback_event_handler():
    """Handle incoming Lark messages"""
    try:
        # Get message data
        data = request.get_json()
        
        # Verify token
        challenge = data.get("challenge")
        if challenge:
            print("DEBUG: Challenge received, responding with challenge")
            return jsonify({"challenge": challenge})
        
        # Extract message content
        message_data = data.get("event", {}).get("message", {})
        text = message_data.get("content")
        
        if not text:
            return jsonify({"code": 0})
        
        # Parse message content
        try:
            content_dict = json.loads(text)
            text = content_dict.get("text", "").strip()
        except:
            pass
        
        if not text:
            return jsonify({"code": 0})
        
        # Get sender info
        sender = data.get("event", {}).get("sender", {})
        user_open_id = sender.get("id")
        
        print(f"DEBUG: Received message from {user_open_id}: {text}")
        
        # Initialize response
        response_text = None
        
        # ========== PERFORMANCE COMMANDS ==========
        if text.lower().startswith("perf"):
            print(f"DEBUG: Detected performance command")
            try:
                # Fetch user data if not already fetched
                temp_tracker = PerformanceTracker(
                    app_token=os.getenv("LARK_BASE_APP_TOKEN"),
                    performance_table_id=os.getenv("LARK_BASE_PERFORMANCE_TABLE_ID"),
                    projections_table_id=os.getenv("LARK_BASE_PROJECTIONS_TABLE_ID"),
                    tenant_access_token=token_manager.get_token(),
                    host=os.getenv("LARK_HOST", "https://open.larksuite.com")
                )
                user_data = temp_tracker.get_user_data()
                performance_commands_handler = PerformanceCommands(temp_tracker, user_data)
                
                response_text = performance_commands_handler.handle_performance_command(text, user_open_id)
            except Exception as e:
                print(f"ERROR: Performance command error: {e}")
                response_text = f"❌ Error fetching performance data: {str(e)}"
        
        # ========== COMMISSION CALCULATOR ==========
        elif text and any(text.upper().startswith(platform) for platform in ["GINSU", "BING", "YAHOO", "RSOC"]):
            print("DEBUG: Detected commission calculation command")
            response_text = calculate_commission(text, user_open_id)
        
        # ========== CREATIVE TRACKER ==========
        elif text.lower().startswith("creative"):
            print("DEBUG: Detected creative tracker command")
            try:
                command = parse_creative_command(text)
                
                if command and command.get("type") == "help":
                    response_text = get_creative_help()
                elif command and command.get("type") == "test":
                    try:
                        from meegle_api import MeegleClient
                        client = MeegleClient()
                        result = client.test_connection()
                        response_text = "✅ Meegle connection successful!"
                    except Exception as e:
                        response_text = f"❌ Meegle connection failed: {str(e)}"
                elif command and command.get("type") == "count":
                    response_text = count_creatives_by_creator(command["creator"], command["time_period"], user_open_id)
                elif command and command.get("type") == "language":
                    response_text = count_creatives_by_language(command["language"], command["time_period"])
                elif command and "error" in command:
                    response_text = command["error"]
                else:
                    response_text = get_creative_help()
            except Exception as e:
                print(f"ERROR: Creative tracker error: {e}")
                response_text = f"❌ Error in creative tracker: {str(e)}"
        
        # ========== UNKNOWN COMMAND ==========
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
            print(f"DEBUG: Sending response: {response_text[:100]}...")
            message_api_client.send_text_with_open_id(user_open_id, response_text)
        
        return jsonify({"code": 0})
    
    except Exception as e:
        print(f"ERROR: Exception in callback_event_handler: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"code": 1, "msg": str(e)})


@app.route("/webhook/event", methods=["POST"])
def webhook_event():
    """Webhook endpoint for Lark events"""
    return callback_event_handler()


@app.route("/", methods=["POST"])
def webhook_root():
    """Catch webhook at root path for backward compatibility"""
    return callback_event_handler()


@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "ok",
        "performance_scheduler": "disabled (testing)",
        "user_performance_scheduler": "disabled (testing)"
    })


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    print(f"DEBUG: Starting server on 0.0.0.0:{port}")
    print(f"DEBUG: Performance scheduler: disabled")
    print(f"DEBUG: User performance scheduler: disabled")
    
    # Make sure Flask binds to the port immediately
    try:
        app.run(
            host="0.0.0.0",
            port=port,
            debug=False,
            use_reloader=False,
            threaded=True
        )
    except Exception as e:
        print(f"CRITICAL ERROR: Failed to start Flask server: {e}")
        import traceback
        traceback.print_exc()
        exit(1)

