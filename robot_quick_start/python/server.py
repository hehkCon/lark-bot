import json
import logging
import os
from flask import Flask, jsonify, request
from api import MessageApiClient
from event import MessageReceiveEvent, UrlVerificationEvent
from commission import calculate_commission

# Load environment variables
APP_ID = os.getenv("APP_ID")
APP_SECRET = os.getenv("APP_SECRET")
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

    # URL verification challenge
    if req_data.get("type") == "url_verification":
        event = UrlVerificationEvent(req_data)
        return jsonify({"challenge": event.challenge})

    # Message received event
    if req_data.get("header", {}).get("event_type") == "im.message.receive_v1":
        event = MessageReceiveEvent(req_data)
        
        # Extract message details
        message = event.event.message
        message_type = message.message_type
        
        # Only handle text messages
        if message_type != "text":
            logging.info(f"Ignoring non-text message type: {message_type}")
            return jsonify({"message": "ignored"}), 200
        
        # Parse message content
        content = json.loads(message.content)
        text = content.get("text", "").strip()
        
        # Extract sender information
        sender = event.event.sender
        user_open_id = sender.sender_id.get("open_id")
        
        logging.info(f"Received message from {user_open_id}: {text}")
        print(f"DEBUG: Received message from {user_open_id}: {text}")
        
        # Calculate commission with user mention
        response_text = calculate_commission(text, user_id=user_open_id)
        
        # Send response
        try:
            message_api_client.send_text_with_open_id(user_open_id, response_text)
            logging.info(f"Sent response to {user_open_id}")
        except Exception as e:
            logging.error(f"Failed to send message: {e}")
            return jsonify({"error": str(e)}), 500
        
        return jsonify({"message": "success"}), 200

    # Unknown event type
    logging.warning(f"Unknown event type: {req_data.get('header', {}).get('event_type')}")
    return jsonify({"message": "unknown event"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)

