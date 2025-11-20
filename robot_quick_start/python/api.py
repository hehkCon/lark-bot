import requests
import json
import time

class MessageApiClient:
    def __init__(self, app_id, app_secret, host):
        self.app_id = app_id
        self.app_secret = app_secret
        self.host = host
        self.tenant_access_token = None
        self.token_expiry = 0  # Unix timestamp when token expires

    def fetch_tenant_access_token(self):
        token_url = f"{self.host}/open-apis/auth/v3/tenant_access_token/internal"
        headers = {"Content-Type": "application/json"}
        data = {
            "app_id": self.app_id,
            "app_secret": self.app_secret,
        }
        response = requests.post(token_url, headers=headers, json=data)
        response.raise_for_status()
        resp_json = response.json()
        self.tenant_access_token = resp_json.get("tenant_access_token")
        expire_seconds = resp_json.get("expire", 7200)  # usually 2 hours
        self.token_expiry = time.time() + expire_seconds - 60  # refresh 1 min early
        print(f"DEBUG: Fetched new tenant_access_token, expires in {expire_seconds} seconds")

    def ensure_access_token(self):
        if not self.tenant_access_token or time.time() > self.token_expiry:
            self.fetch_tenant_access_token()

    def send(self, receive_id_type, receive_id, msg_type, content):
        self.ensure_access_token()
        token = self.tenant_access_token
        url = f"{self.host}/open-apis/im/v1/messages?receive_id_type={receive_id_type}"

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        # Parse JSON string content to dict to avoid double encode
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
            msg_content = content  # assume dict for other msg types

        payload = {
            "receive_id": receive_id,
            "msg_type": msg_type,
            "content": msg_content,
        }

        print("DEBUG: Sending message payload:", json.dumps(payload))
        print("DEBUG: Authorization header:", headers["Authorization"])

        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()

    def send_text_with_open_id(self, open_id, message):
        return self.send(receive_id_type="open_id", receive_id=open_id, msg_type="text", content=message)

