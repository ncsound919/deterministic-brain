from __future__ import annotations
import uuid

class BrowserSession:
    def __init__(self, url: str = 'https://example.com'):
        self.session_id = str(uuid.uuid4())[:8]
        self.url = url
        self.history: list = []
        self.active = True

    def record_action(self, action: dict) -> None:
        self.history.append(action)

    def close(self) -> None:
        self.active = False

    def to_dict(self) -> dict:
        return {'session_id': self.session_id, 'url': self.url,
                'history': self.history, 'active': self.active}
