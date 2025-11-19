#!/usr/bin/env python3.8

import os
import logging
import json
import requests
from api import MessageApiClient
from event import MessageReceiveEvent, UrlVerificationEvent, EventManager
from flask import Flask, jsonify
from dotenv import load_dotenv, find_dotenv
from commission import calculate_commission

# Load env parameters from file named .env
load_dotenv(find_dotenv())

app = Flask(__name__)

# Load from env
APP_ID = os.getenv("APP_ID")
APP_SECRET = os.getenv("APP_SECRET")
VERIFICATION_TOKEN = os.getenv("VERIFICATION_TOKEN")
ENCRYPT_KEY = os.getenv("ENCRYPT_KEY")
LARK_HOST = os.getenv("LARK_HOST")

# Initialize services
message_api_client = MessageApiClient(APP_ID, APP_SECRET, LARK_HOST)
event_manager = EventManager()


@event_manager.register("url_verification")
def request_url_verify_handler(req_data: UrlVerificationEvent):
    # URL verification, return challenge if token matches
    if req_data.event.token != VERIFICATION_TOKEN:
        raise Exception("VERIFICATION_TOKEN is invalid")
    return jsonify({"challenge": req_data.event.challenge})


@event_manager.register("im.message.receive_v1")
def message_receive_event_handler(req_data: MessageReceiveEvent):
    sender_id = req_data.event.sender.sender_id
    message = req_data.event.message
    if message.message_type != "text":
        logging.warning("Other types of messages have not been processed yet")
        return jsonify()
    
    open_id = sender_id.open_id
    
    try:
        content_obj = json.loads(message.content)
        text_content = content_obj.get("text", "")
    except Exception as e:
        logging.error(f"Error parsing message content as JSON: {e}")
        text_content = message.content

    logging.debug(f"DEBUG: Received message from open_id={open_id}, content={text_content}")

    # Calculate commission based on user input
    response = calculate_commission(text_content)
    
    logging.debug(f"DEBUG: Calculated commission response: {response}")

    # Send response back to user
    try:
        message_api_client.send_text_with_open_id(open_id, response)
    except Exception as e:
        logging.error(f"Error sending message: {e}")
        return jsonify({"error": str(e)}), 500
    
    return jsonify()


@app.errorhandler(Exception)
def msg_error_handler(ex):
    logging.error(f"Unhandled Exception: {ex}")
    response = jsonify(message=str(ex))
    response.status_code = (
        ex.response.status_code if isinstance(ex, requests.HTTPError) else 500
    )
    return response


@app.route("/", methods=["POST"])
def callback_event_handler():
    # Initialize callback instance and handle events
    event_handler, event = event_manager.get_handler_with_event(VERIFICATION_TOKEN, ENCRYPT_KEY)
    return event_handler(event)


if __name__ == "__main__":
    port = int(os.getenv("PORT", 3000))
    app.run(host="0.0.0.0", port=port, debug=True)

