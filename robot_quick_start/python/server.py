#!/usr/bin/env python3.8

import os
import logging
import json
from flask import Flask, jsonify, request
from dotenv import load_dotenv, find_dotenv
from api import MessageApiClient, APP_ID, APP_SECRET, LARK_HOST
from event import MessageReceiveEvent, UrlVerificationEvent, EventManager
from commission import calculate_commission  # Your commission calculator logic here

# Load environment variables
load_dotenv(find_dotenv())

app = Flask(__name__)

APP_ID = os.getenv("APP_ID")
APP_SECRET = os.getenv("APP_SECRET")
VERIFICATION_TOKEN = os.getenv("VERIFICATION_TOKEN")
ENCRYPT_KEY = os.getenv("ENCRYPT_KEY")
LARK_HOST = os.getenv("LARK_HOST")

message_api_client = MessageApiClient(APP_ID, APP_SECRET, LARK_HOST)
event_manager = EventManager()

@app.route("/", methods=["GET"])
def health_check():
    return "Lark Commission Bot is running", 200

@event_manager.register("url_verification")
def request_url_verify_handler(req_data: UrlVerificationEvent):
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

    response = calculate_commission(text_content)
    logging.debug(f"DEBUG: Calculated commission response: {response}")

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
        ex.response.status_code if hasattr(ex, "response") and ex.response is not None else 500
    )
    return response

@app.route("/", methods=["POST"])
def callback_event_handler():
    event_handler, event = event_manager.get_handler_with_event(VERIFICATION_TOKEN

