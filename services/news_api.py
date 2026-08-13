"""
Adapter untuk NewsData.io API (free tier: 200 req/hari).

Digunakan sebagai sumber berita REAL untuk kategori:
- Edukasi Kesehatan (health_edu)

Endpoint: https://newsdata.io/api/1/news
Free tier limit: 200 requests / hari.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

import requests

logger = logging.getLogger(__name__)

NEWSDATA_API_KEY = os.getenv("NEWSDATA_API_KEY", "")
NEWSDATA_BASE = os.getenv("NEWSDATA_BASE_URL", "https://newsdata.io/api/1")
DEFAULT_TIMEOUT = int(os.getenv("DEFAULT_TIMEOUT_SECONDS", "10"))


class NewsDataAPIError(Exception):
    """Error umum saat berkomunikasi dengan NewsData.io."""


class NewsDataAPIKeyMissingError(NewsDataAPIError):
    """API Key NewsData.io tidak tersedia."""


@dataclass(frozen=True, slots=True)
class NewsDataArticle:
    """Representasi artikel dari response NewsData.io."""

    title: str
    description: str | None
    url: str
    image_url: str | None
    published_at: str
    source_name: str

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> "NewsDataArticle":
        return cls(
            title=raw.get("title", "Tanpa Judul"),
            description=raw.get("description") or raw.get("content", ""),
            url=raw.get("link", ""),
            image_url=raw.get("image_url"),
            published_at=raw.get("pubDate", ""),
            source_name=raw.get("source_id", "Unknown"),
        )


class NewsDataClient:
    """
    Client tipis di atas NewsData.io REST API.

    Free tier: 200 requests / hari.
    Gunakan instance ini lewat dependency injection ke ContentService.
    """

    def __init__(
        self,
        api_key: str | None = None,
        session: requests.Session | None = None,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        self._api_key = api_key or NEWSDATA_API_KEY
        self._session = session or requests.Session()
        self._timeout = timeout

    # -----------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------
    def search(
        self,
        query: str,
        max_results: int = 5,
        language: str = "en",
        category: str | None = None,
    ) -> list[NewsDataArticle]:
        """
        Cari artikel berita berdasarkan query.

        Args:
            query: Kata kunci pencarian
            max_results: Maksimal artikel (1-10 per page, free tier)
            language: Kode bahasa (en, id, dll)
            category: Kategori NewsData.io (health, sports, technology, dll)

        Returns:
            List NewsDataArticle. Kosong kalau API key tidak ada atau error.
        """
        if not self._api_key:
            logger.warning("NEWSDATA_API_KEY tidak tersedia, skip pencarian berita.")
            raise NewsDataAPIKeyMissingError("NEWSDATA_API_KEY belum di-set di environment")

        url = f"{NEWSDATA_BASE}/news"
        params: dict[str, Any] = {
            "apikey": self._api_key,
            "q": query,
            "language": language,
            "size": min(max_results, 10),  # NewsData.io max 10 per request (free)
        }
        if category:
            params["category"] = category

        try:
            response = self._session.get(url, params=params, timeout=self._timeout)
        except requests.RequestException as exc:
            logger.error("Request NewsData.io gagal: %s", exc)
            raise NewsDataAPIError(f"Gagal terhubung ke NewsData.io: {exc}") from exc

        if response.status_code == 401:
            raise NewsDataAPIError("NewsData.io API Key tidak valid (401 Unauthorized)")
        if response.status_code == 429:
            raise NewsDataAPIError("NewsData.io rate limit tercapai (429 Too Many Requests)")
        if response.status_code != 200:
            raise NewsDataAPIError(f"NewsData.io mengembalikan status {response.status_code}")

        try:
            data = response.json()
        except ValueError as exc:
            raise NewsDataAPIError("Response NewsData.io bukan JSON valid") from exc

        # NewsData.io return structure: {"status": "success", "results": [...]}
        articles = data.get("results") or []
        logger.info("NewsData.io: ditemukan %s artikel untuk query '%s'", len(articles), query)
        return [NewsDataArticle.from_raw(a) for a in articles]

    def search_health(self, topic: str | None = None, max_results: int = 5) -> list[NewsDataArticle]:
        """
        Shortcut untuk cari berita kesehatan & fitness.
        """
        query = topic if topic else "health fitness exercise wellness"
        return self.search(query=query, max_results=max_results, language="en", category="health")

    def close(self) -> None:
        """Tutup session. Panggil saat bot shutdown."""
        self._session.close()