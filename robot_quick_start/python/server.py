import json
import logging
import os
from flask import Flask, jsonify, request
from api import MessageApiClient
from commission import calculate_commission

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
        
        # Calculate commission
        response_text = calculate_commission(text, user_id=user_open_id)
        
        print(f"DEBUG: Response text: {response_text}")
        
        # Send response
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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)

