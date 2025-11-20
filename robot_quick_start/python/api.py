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
        # Start background refresh thread
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
            # Set expiry a bit early to refresh proactively
            expire_in = data.get("expire", 7200)
            self.expiry_time = time.time() + expire_in - 120
            print(f"DEBUG: Fetched token, expires in {expire_in}s at {self.expiry_time}")

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
                # Sleep until near token expiration
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
        url = f"{self.host}/open-apis/im/v1/messages?receive_id_type={receive_id_type}"
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer " + token,
        }

        # Prepare content: parse JSON string if needed
        if msg_type == "text" and isinstance(content, str):
            try:
                content_obj = json.loads(content)
                if isinstance(content_obj, dict) and "text" in content_obj:
                    msg_content = content_obj
                else:
                    msg_content = {"text": content}
            except json.JSONDecodeError:
                msg_content = {"text": content}
        else:
            msg_content = content

        payload = {
            "receive_id": receive_id,
            "msg_type": msg_type,
            "content": msg_content,
        }

        print(f"DEBUG: Sending to {url} with token {token}")
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()

    def send_text_with_open_id(self, open_id, message):
        return self.send("open_id", open_id, "text", message)

