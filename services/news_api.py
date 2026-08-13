"""
Adapter untuk GNews API (free tier: 100 req/hari).

Modul ini jadi feeder berita REAL dari internet untuk kategori
yang butuh data aktual (sepatu branded, kesehatan, dll).
Hasilnya diteruskan ke Gemini untuk diringkas & diterjemahkan
ke bahasa Indonesia gaya Discord.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

import requests

logger = logging.getLogger(__name__)

GNEWS_API_KEY = os.getenv("GNEWS_API_KEY", "")
GNEWS_BASE = os.getenv("GNEWS_BASE_URL", "https://gnews.io/api/v4")
DEFAULT_TIMEOUT = int(os.getenv("DEFAULT_TIMEOUT_SECONDS", "10"))


class NewsAPIError(Exception):
    """Error umum saat berkomunikasi dengan GNews."""


class NewsAPIKeyMissingError(NewsAPIError):
    """API Key GNews tidak tersedia."""


@dataclass(frozen=True, slots=True)
class NewsArticle:
    """Representasi artikel yang sudah disederhanakan dari response GNews."""

    title: str
    description: str
    url: str
    image: str | None
    published_at: str
    source_name: str

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> "NewsArticle":
        source = raw.get("source", {})
        return cls(
            title=raw.get("title", "Tanpa Judul"),
            description=raw.get("description", ""),
            url=raw.get("url", ""),
            image=raw.get("image"),
            published_at=raw.get("publishedAt", ""),
            source_name=source.get("name", "Unknown"),
        )


class GNewsClient:
    """
    Client tipis di atas GNews REST API.

    Free tier limit: 100 requests / hari.
    Gunakan instance ini lewat dependency injection ke ContentService,
    jangan buat instance baru di banyak tempat.
    """

    def __init__(
        self,
        api_key: str | None = None,
        session: requests.Session | None = None,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        self._api_key = api_key or GNEWS_API_KEY
        self._session = session or requests.Session()
        self._timeout = timeout

    # -----------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------
    def search(
        self,
        query: str,
        max_results: int = 3,
        lang: str = "en",
        country: str | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> list[NewsArticle]:
        """
        Cari artikel berita berdasarkan query.

        Args:
            query: Kata kunci pencarian (contoh: "Li-Ning sneakers", "health fitness")
            max_results: Maksimal artikel (1-10, free tier biasanya max 10)
            lang: Kode bahasa (en, id, dll)
            country: Kode negara (us, cn, id, dll) — opsional
            from_date: YYYY-MM-DD — opsional
            to_date: YYYY-MM-DD — opsional

        Returns:
            List NewsArticle. Kosong kalau API key tidak ada atau error.
        """
        if not self._api_key:
            logger.warning("GNEWS_API_KEY tidak tersedia, skip pencarian berita.")
            raise NewsAPIKeyMissingError("GNEWS_API_KEY belum di-set di environment")

        url = f"{GNEWS_BASE}/search"
        params: dict[str, Any] = {
            "q": query,
            "lang": lang,
            "max": min(max_results, 10),  # GNews free tier max 10
            "apikey": self._api_key,
        }
        if country:
            params["country"] = country
        if from_date:
            params["from"] = from_date
        if to_date:
            params["to"] = to_date

        try:
            response = self._session.get(url, params=params, timeout=self._timeout)
        except requests.RequestException as exc:
            logger.error("Request GNews gagal: %s", exc)
            raise NewsAPIError(f"Gagal terhubung ke GNews: {exc}") from exc

        if response.status_code == 401:
            raise NewsAPIError("GNews API Key tidak valid (401 Unauthorized)")
        if response.status_code == 429:
            raise NewsAPIError("GNews rate limit tercapai (429 Too Many Requests)")
        if response.status_code != 200:
            raise NewsAPIError(f"GNews mengembalikan status {response.status_code}")

        try:
            data = response.json()
        except ValueError as exc:
            raise NewsAPIError("Response GNews bukan JSON valid") from exc

        articles = data.get("articles", [])
        logger.info("GNews: ditemukan %s artikel untuk query '%s'", len(articles), query)
        return [NewsArticle.from_raw(a) for a in articles]

    def search_sneakers(self, brand: str | None = None, max_results: int = 3) -> list[NewsArticle]:
        """
        Shortcut untuk cari berita sepatu/sneakers.
        Kalau brand tidak diisi, cari generic sneakers news.
        """
        query = f"{brand} sneakers shoes" if brand else "sneakers shoes sportswear"
        return self.search(query=query, max_results=max_results, lang="en")

    def search_health(self, topic: str | None = None, max_results: int = 3) -> list[NewsArticle]:
        """
        Shortcut untuk cari berita kesehatan & fitness.
        """
        query = f"{topic} health fitness exercise" if topic else "health fitness exercise tips"
        return self.search(query=query, max_results=max_results, lang="en")

    def close(self) -> None:
        """Tutup session. Panggil saat bot shutdown."""
        self._session.close()