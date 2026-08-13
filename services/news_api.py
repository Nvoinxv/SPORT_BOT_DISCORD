# services/news_api.py  (OPSIONAL — hanya kalau mau data real)
import os
import requests
from dataclasses import dataclass

GNEWS_API_KEY = os.getenv("GNEWS_API_KEY", "")
GNEWS_BASE = "https://gnews.io/api/v4"

@dataclass(frozen=True, slots=True)
class NewsArticle:
    title: str
    description: str
    url: str
    image: str | None
    published_at: str

class GNewsClient:
    def __init__(self, api_key: str = GNEWS_API_KEY) -> None:
        self._key = api_key

    def search(self, query: str, max_results: int = 3, lang: str = "en") -> list[NewsArticle]:
        if not self._key:
            return []
        url = f"{GNEWS_BASE}/search"
        params = {
            "q": query,
            "lang": lang,
            "max": max_results,
            "apikey": self._key,
        }
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        articles = data.get("articles", [])
        return [
            NewsArticle(
                title=a["title"],
                description=a.get("description", ""),
                url=a["url"],
                image=a.get("image"),
                published_at=a.get("publishedAt", ""),
            )
            for a in articles
        ]