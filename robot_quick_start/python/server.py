import json
import logging
import os
from flask import Flask, jsonify, request
from api import MessageApiClient
from commission import calculate_commission
from creative_tracker import parse_creative_command, count_creatives_by_creator, count_creatives_by_language, get_creative_help

# Load environment variables
APP_ID = os.getenv("APP_ID")
APP_SECRET = os.getenv("APP_SECRET")
VERIFICATION_TOKEN = os.getenv("VERIFICATION_TOKEN", "")
LARK_HOST = os.getenv("LARK_HOST", "https://open.larksuite.com")

# Debug prints
print(f"DEBUG: APP_ID={APP_ID}")
print(f"DEBUG: APP_SECRET={'SET' if APP_SECRET else 'NOT SET'}")
print(f"DEBUG: LARK_HOST={LARK_HOST}")

app = Flask(__name__)

# Initialize message client
message_api_client = MessageApiClient(APP_ID, APP_SECRET, LARK_HOST)

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
    
    # Enhanced debugging
    print(f"DEBUG: Received POST data: {json.dumps(req_data, indent=2)}")

    # URL verification challenge
    if req_data.get("type") == "url_verification":
        challenge = req_data.get("challenge")
        print(f"DEBUG: URL verification challenge received")
        return jsonify({"challenge": challenge})

    # Extract event ID and check for duplicates
    event_id = req_data.get("header", {}).get("event_id")
    
    # DEDUPLICATION: Check if we've already processed this event
    if event_id in processed_events:
        print(f"DEBUG: Duplicate event {event_id} - ignoring (already processed)")
        return jsonify({"message": "duplicate"}), 200
    
    # Add to processed events
    processed_events.add(event_id)
    
    # Keep only last 1000 event IDs to prevent memory issues
    if len(processed_events) > 1000:
        # Remove oldest event
        processed_events.clear()
    
    print(f"DEBUG: Processing new event {event_id}")

    # Extract event type
    event_type = req_data.get("header", {}).get("event_type")
    print(f"DEBUG: Event type: {event_type}")

    # Message received event
    if event_type == "im.message.receive_v1":
        # Extract message details directly from req_data
        event_data = req_data.get("event", {})
        message = event_data.get("message", {})
        message_type = message.get("message_type")
        
        print(f"DEBUG: Message type: {message_type}")
        
        # Only handle text messages
        if message_type != "text":
            logging.info(f"Ignoring non-text message type: {message_type}")
            return jsonify({"message": "ignored"}), 200
        
        # Parse message content
        content_str = message.get("content", "{}")
        content = json.loads(content_str)
        text = content.get("text", "").strip()
        
        # Extract sender information
        sender = event_data.get("sender", {})
        sender_id = sender.get("sender_id", {})
        user_open_id = sender_id.get("open_id")
        
        logging.info(f"Received message from {user_open_id}: {text}")
        print(f"DEBUG: Received message from {user_open_id}: {text}")
        
        # Determine response based on command type
        response_text = None
        
        # Check if it's a creative tracking command
        if text.lower().startswith("creative"):
            print(f"DEBUG: Detected creative command")
            parsed = parse_creative_command(text)
            
            if parsed is None:
                # Not a valid creative command
                response_text = "❌ Invalid creative command. Type 'creative help' for usage."
            elif "error" in parsed:
                response_text = parsed["error"]
            elif parsed.get("type") == "help":
                response_text = get_creative_help()
            elif parsed.get("type") == "test":
                # Test Meegle API connection
                try:
                    from meegle_api import MeegleClient
                    client = MeegleClient()
                    result = client.test_connection()
                    
                    items = result.get("data", [])
                    item_count = len(items)
                    
                    first_item = items[0] if items else None
                    item_name = first_item.get("name", "N/A") if first_item else "No items"
                    item_id = first_item.get("id", "N/A") if first_item else "N/A"
                    
                    response_text = f"""✅ Meegle API Connected!

Items retrieved: {item_count}
Response keys: {list(result.keys())}

First item:
- ID: {item_id}
- Name: {item_name}

Full response structure working!"""
                    
                except Exception as e:
                    import traceback
                    response_text = f"❌ Meegle API test failed: {str(e)}\n\nTraceback:\n{traceback.format_exc()}"
            elif parsed["type"] in ["count", "stats"]:
                response_text = count_creatives_by_creator(
                    parsed["creator"],
                    parsed["time_period"],
                    lark_user_id=user_open_id
                )
            elif parsed["type"] == "language":
                response_text = count_creatives_by_language(
                    parsed["language"],
                    parsed["time_period"]
                )
            else:
                response_text = "❌ Unknown creative command"
        else:
            # Commission calculation (existing logic) - ONLY if NOT a creative command
            response_text = calculate_commission(text, user_id=user_open_id)
        
        print(f"DEBUG: Response text: {response_text}")
        
        # Send response ONCE - single send point
        if response_text:
            try:
                message_api_client.send_text_with_open_id(user_open_id, response_text)
                logging.info(f"Sent response to {user_open_id}")
                print(f"DEBUG: Successfully sent response")
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

