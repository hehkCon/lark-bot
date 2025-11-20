#!/usr/bin/env python3.8

import os
import logging
import json
from flask import Flask, jsonify, request
from dotenv import load_dotenv

# Load environment variables explicitly from Render secret file path
load_dotenv(dotenv_path="/etc/secrets/.env")  # Adjust this path if needed

# Debug prints to verify environment variables loaded correctly
print(f"DEBUG: APP_ID={os.getenv('APP_ID')}")
print(f"DEBUG: APP_SECRET={'SET' if os.getenv('APP_SECRET') else 'NOT SET'}")
print(f"DEBUG: LARK_HOST={os.getenv('LARK_HOST')}")

from api import MessageApiClient
from event import MessageReceiveEvent, UrlVerificationEvent, EventManager
from commission import calculate_commission  # your commission logic

app = Flask(__name__)

# Fetch credentials from environment variables
APP_ID = os.getenv("APP_ID")
APP_SECRET = os.getenv("APP_SECRET")
VERIFICATION_TOKEN = os.getenv("VERIFICATION_TOKEN")
ENCRYPT_KEY = os.getenv("ENCRYPT_KEY", "")
LARK_HOST = os.getenv("LARK_HOST")

# Instantiate the message API client with token auto-refresh
message_api_client = MessageApiClient(APP_ID, APP_SECRET, LARK_HOST)
event_manager = EventManager()

@app.route("/", methods=["GET"])
def health_check():
    return "Lark Commission Bot is running", 200

@event_manager.register("url_verification")
def handle_url_verification(req_data: UrlVerificationEvent):
    if req_data.event.token != VERIFICATION_TOKEN:
        raise Exception("Invalid VERIFICATION_TOKEN")
    return jsonify({"challenge": req_data.event.challenge})

@event_manager.register("im.message.receive_v1")
def handle_message_receive(req_data: MessageReceiveEvent):
    sender_id = req_data.event.sender.sender_id
    message = req_data.event.message

    if message.message_type != "text":
        logging.warning("Unhandled message type received")
        return jsonify()

    open_id = sender_id.open_id

    try:
        content_obj = json.loads(message.content)
        text_content = content_obj.get("text", "")
    except Exception as e:
        logging.error(f"JSON parse error: {e}")
        text_content = message.content

    logging.debug(f"Message from open_id={open_id}: {text_content}")

    response = calculate_commission(text_content)

    try:
        message_api_client.send_text_with_open_id(open_id, response)
    except Exception as e:
        logging.error(f"Failed to send message: {e}")
        return jsonify({"error": str(e)}), 500

    return jsonify()

@app.errorhandler(Exception)
def handle_exceptions(ex):
    logging.error(f"Unexpected error: {ex}")
    status_code = ex.response.status_code if hasattr(ex, "response") and ex.response else 500
    return jsonify(message=str(ex)), status_code

@app.route("/", methods=["POST"])
def handle_callback():
    event_handler, event = event_manager.get_handler_with_event(VERIFICATION_TOKEN, ENCRYPT_KEY or "")
    return event_handler(event)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 3000))
    app.run(host="0.0.0.0", port=port, debug=True)

