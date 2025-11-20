import requests
import json

class MessageApiClient:
    def __init__(self, app_id, app_secret, host):
        self.app_id = app_id
        self.app_secret = app_secret
        self.host = host
        self.tenant_access_token = None
        # Initialize token manager or similar here

    def send(self, receive_id_type, receive_id, msg_type, content):
        token = self.tenant_access_token
        url = f"{self.host}/open-apis/im/v1/messages?receive_id_type={receive_id_type}"

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        # If content is a JSON string (from commission.py), parse to dict to avoid double encoding
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
            msg_content = content  # assume dict for other types

        payload = {
            "receive_id": receive_id,
            "msg_type": msg_type,
            "content": msg_content,
        }

        print("DEBUG: Sending message payload:", json.dumps(payload))  # Debug log for payload
        print("DEBUG: Auth header:", headers.get("Authorization"))     # Debug log for auth token

        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()

    def send_text_with_open_id(self, open_id, message):
        return self.send(receive_id_type="open_id", receive_id=open_id, msg_type="text", content=message)

