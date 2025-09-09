import requests

class WhatsAppBridge:
    def __init__(self, base_url, session_name="default"):
        self.base_url = base_url.rstrip("/")
        self.session = session_name

    def list_sessions(self):
        return requests.get(f"{self.base_url}/sessions").json()

    def get_qr(self):
        return requests.get(f"{self.base_url}/qr?session={self.session}").json()

    def send_message(self, number_or_group, message):
        return requests.post(f"{self.base_url}/kirim-pesan",
                             json={"number": number_or_group, "message": message, "session": self.session}).json()

    def list_groups(self):
        return requests.get(f"{self.base_url}/groups?session={self.session}").json()

    def fetch_groups(self):
        return requests.get(f"{self.base_url}/fetch-groups?session={self.session}").json()
