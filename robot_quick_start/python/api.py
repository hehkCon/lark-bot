#! /usr/bin/env python3.8
import os
import threading
import time
import requests
import json

APP_ID = os.getenv("APP_ID")
APP_SECRET = os.getenv("APP_SECRET")
LARK_HOST = os.getenv("LARK_HOST")

TENANT_ACCESS_TOKEN_URI = "/open-apis/auth/v3/tenant_access_token/internal"
MESSAGE_URI = "/open-apis/im/v1/messages"


class TokenManager:
    def __init__(self, app_id, app_secret, host):
        self.app_id = app_id
        self.app_secret = app_secret
        self.host = host
        self.token = None
        self.expiry_time = 0
        self.lock = threading.Lock()
        print(f"DEBUG: TokenManager initialized with app_id length={len(app_id)}, host={host}")

    def fetch_token(self):
        url = f"{self.host}{TENANT_ACCESS_TOKEN_URI}"
        headers = {"Content-Type": "application/json; charset=utf-8"}
        payload = {"app_id": self.app_id, "app_secret": self.app_secret}

        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        with self.lock:
            self.token = data.get("tenant_access_token")
            self.expiry_time = time.time() + data.get("expire", 7200) - 120  # refresh 2 mins early
        print(f"DEBUG: Fetched tenant_access_token: {self.token}, expires at {self.expiry_time}")

    def get_token(self):
        with self.lock:
            if not self.token or time.time() > self.expiry_time:
                print("DEBUG: Token expired or not fetched, fetching new one")
                self.fetch_token()
            return self.token

    def start_auto_refresh(self):
        def refresh_loop():
            while True:
                try:
                    self.fetch_token()
                except Exception as e:
                    print(f"ERROR refreshing token: {e}")
                sleep_time = max(60, self.expiry_time - time.time() - 60)
                time.sleep(sleep_time)
        thread = threading.Thread(target=refresh_loop, daemon=True)
        thread.start()


class MessageApiClient(object):
    def __init__(self, app_id, app_secret, lark_host):
        self._app_id = app_id
        self._app_secret = app_secret
        self._lark_host = lark_host
        self.token_manager = TokenManager(app_id, app_secret, lark_host)
        self.token_manager.start_auto_refresh()

    @property
    def tenant_access_token(self):
        return self.token_manager.get_token()

    def send_text_with_open_id(self, open_id, content):
        self.send("open_id", open_id, "text", content)

def send(self, receive_id_type, receive_id, msg_type, content):  
    token = self.tenant_access_token
    print(f"DEBUG: Authorization header token: {token}")

    url = "{}{}?receive_id_type={}".format(
        self._lark_host, MESSAGE_URI, receive_id_type
    )
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + token,
    }

    if msg_type == "text" and isinstance(content, str):
        msg_content = json.dumps({"text": content})
    else:
        msg_content = json.dumps(content)

    req_body = {
        "receive_id": receive_id,
        "content": msg_content,
        "msg_type": msg_type,
    }

    print(f"DEBUG: Sending POST to {url}")
    print(f"DEBUG: Headers: {headers}")
    print(f"DEBUG: Payload: {json.dumps(req_body)}")

    resp = requests.post(url=url, headers=headers, json=req_body)
    MessageApiClient._check_error_response(resp)

    @staticmethod
    def _check_error_response(resp):
        if resp.status_code != 200:
            resp.raise_for_status()
        response_dict = resp.json()
        code = response_dict.get("code", -1)
        if code != 0:
            raise LarkException(code=code, msg=response_dict.get("msg"))


class LarkException(Exception):
    def __init__(self, code=0, msg=None):
        self.code = code
        self.msg = msg

    def __str__(self) -> str:
        return "{}:{}".format(self.code, self.msg)

    __repr__ = __str__

