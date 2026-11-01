"""Small Threads Graph API client. No browser or local login session is used."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import requests


BASE = "https://graph.threads.net/v1.0"
KST = ZoneInfo("Asia/Seoul")


class ThreadsAPI:
    def __init__(self, access_token: str, session: requests.Session | None = None):
        if not access_token:
            raise ValueError("Threads access token is required")
        self.token = access_token
        self.session = session or requests.Session()

    def request(self, method: str, path: str, **kwargs) -> dict:
        headers = {"Authorization": f"Bearer {self.token}"}
        headers.update(kwargs.pop("headers", {}))
        response = self.session.request(
            method, f"{BASE}/{path.lstrip('/')}", headers=headers, timeout=40, **kwargs
        )
        response.raise_for_status()
        return response.json()

    def identity(self) -> dict:
        return self.request("GET", "me", params={"fields": "id,username"})

    def recent(self, limit: int = 50) -> list[dict]:
        result = self.request(
            "GET", "me/threads",
            params={"fields": "id,username,text,timestamp,permalink,is_quote_post", "limit": limit},
        )
        return result.get("data", [])

    def today(self, now: datetime) -> list[dict]:
        date = now.astimezone(KST).date()
        posts = []
        for post in self.recent():
            timestamp = datetime.fromisoformat(post["timestamp"].replace("Z", "+00:00"))
            if timestamp.astimezone(KST).date() == date:
                posts.append(post)
        return posts

    def create_image(self, text: str, image_url: str, alt_text: str) -> str:
        data = self.request("POST", "me/threads", data={
            "media_type": "IMAGE", "text": text, "image_url": image_url,
            "alt_text": alt_text,
        })
        return data["id"]

    def create_quote(self, text: str, quote_post_id: str) -> str:
        data = self.request("POST", "me/threads", data={
            "media_type": "TEXT", "text": text, "quote_post_id": quote_post_id,
        })
        return data["id"]

    def publish(self, container_id: str) -> dict:
        published = self.request("POST", "me/threads_publish", data={"creation_id": container_id})
        return self.request(
            "GET", published["id"],
            params={"fields": "id,username,text,permalink,timestamp,is_quote_post"},
        )

    def refresh(self) -> str:
        result = self.request(
            "GET", "refresh_access_token", params={"grant_type": "th_refresh_token"}
        )
        return result["access_token"]
