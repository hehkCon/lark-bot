import requests
import json
import threading
import time

class TokenManager:
    def __init__(self, app_id, app_secret, host):
        self.app_id = app_id
        self.app_secret = app_secret
        self.host = host
        self.token = None
        self.expiry_time = 0
        self.lock = threading.Lock()
        # Start token auto-refresh thread
        self.start_auto_refresh()

    def fetch_token(self):
        url = f"{self.host}/open-apis/auth/v3/tenant_access_token/internal"
        headers = {"Content-Type": "application/json"}
        payload = {"app_id": self.app_id, "app_secret": self.app_secret}

        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()

        with self.lock:
            self.token = data.get("tenant_access_token")
            expire_in = data.get("expire", 7200)
            self.expiry_time = time.time() + expire_in - 120  # Refresh 2 mins early

            token_preview = self.token[:10] + "..." + self.token[-10:] if self.token else "None"
            print(f"DEBUG: Fetched token ({token_preview}), expires in {expire_in}s at {self.expiry_time}")

    def get_token(self):
        with self.lock:
            if not self.token or time.time() > self.expiry_time:
                self.fetch_token()
            return self.token

    def start_auto_refresh(self):
        def refresh_loop():
            while True:
                try:
                    self.fetch_token()
                except Exception as e:
                    print(f"ERROR: Token refresh failed: {e}")
                sleep_time = max(60, self.expiry_time - time.time())
                time.sleep(sleep_time)

        thread = threading.Thread(target=refresh_loop, daemon=True)
        thread.start()


class MessageApiClient:
    def __init__(self, app_id, app_secret, host):
        self.token_manager = TokenManager(app_id, app_secret, host)
        self.host = host

    def send(self, receive_id_type, receive_id, msg_type, content):
        token = self.token_manager.get_token()
        token_preview = token[:10] + "..." + token[-10:] if token else "None"
        print(f"DEBUG: Using token: {token_preview}")

        url = f"{self.host}/open-apis/im/v1/messages?receive_id_type={receive_id_type}"
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer " + token,
        }

        # Robust content parsing for "text" messages
        if msg_type == "text":
            if isinstance(content, dict):
                msg_content = content
            elif isinstance(content, str):
                try:
                    parsed = json.loads(content)
                    if isinstance(parsed, dict) and "text" in parsed:
                        msg_content = parsed
                    else:
                        msg_content = {"text": content}
                except json.JSONDecodeError:
                    msg_content = {"text": content}
            else:
                raise TypeError(f"Unexpected content type for 'text': {type(content)}")
        else:
            # For other message types, assume content is already a dict
            msg_content = content

        # CRITICAL FIX: Serialize content to JSON string
        content_str = json.dumps(msg_content)

        payload = {
            "receive_id": receive_id,
            "msg_type": msg_type,
            "content": content_str,  # JSON string, not dict
        }

        print("DEBUG: Sending message payload:", json.dumps(payload))
        print(f"DEBUG: Authorization header: Bearer {token_preview}")

        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()

    def send_text_with_open_id(self, open_id, message):
        """Send text message to a user (1-on-1 chat)"""
        return self.send("open_id", open_id, "text", message)

    def send_text_with_chat_id(self, chat_id, message):
        """Send text message to a group chat"""
        print(f"DEBUG: Sending message to group chat {chat_id}")
        return self.send("chat_id", chat_id, "text", message)

