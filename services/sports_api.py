"""
Adapter untuk TheSportsDB (free tier).

Modul ini adalah SATU-SATUNYA pintu ke API eksternal TheSportsDB.
Semua kode lain (cogs, scheduler, service lain) wajib memanggil lewat
class `TheSportsDBClient` di sini, bukan lewat `requests` langsung.

Batasan tier gratis TheSportsDB yang sengaja ditangani di modul ini:
- Rate limit: 30 request/menit per key.
- Key gratis ("123") adalah shared test key, bukan key pribadi.
- Endpoint jadwal per tim (next/last event) hanya mengembalikan 1 hasil,
  dan versi gratis hanya menampilkan event kandang (home).
- Tidak ada live score cepat (fitur premium).

Karena keterbatasan di atas, client ini didesain untuk kasus "reminder
pertandingan berikutnya per tim", bukan untuk menarik jadwal satu musim
penuh sekaligus.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import requests
from dotenv import load_dotenv
import os

load_dotenv()

logger = logging.getLogger(__name__)
FREE_TEST_API_KEY = os.getenv("FREE_TEST_API_KEY")
BASE_URL = os.getenv("BASE_URL")
DEFAULT_TIMEOUT_SECONDS = os.getenv("DEFAULT_TIMEOUT_SECONDS")
DEFAULT_MAX_RETRIES = os.getenv("DEFAULT_MAX_RETRIES")
RATE_LIMIT_STATUS_CODE = os.getenv("RATE_LIMIT_STATUS_CODE")
RATE_LIMIT_BACKOFF_SECONDS = os.getenv("RATE_LIMIT_BACKOFF_SECONDS")


class SportsAPIError(Exception):
    """Error umum saat berkomunikasi dengan TheSportsDB."""


class RateLimitExceededError(SportsAPIError):
    """Dilempar saat API mengembalikan status 429 (melebihi limit)."""


class TeamNotFoundError(SportsAPIError):
    """Dilempar saat pencarian tim tidak menemukan hasil."""


@dataclass(frozen=True, slots=True)
class Team:
    """Representasi tim yang sudah disederhanakan dari response mentah."""

    id: str
    name: str
    league: str | None = None
    sport: str | None = None

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> "Team":
        return cls(
            id=raw["idTeam"],
            name=raw["strTeam"],
            league=raw.get("strLeague"),
            sport=raw.get("strSport"),
        )


@dataclass(frozen=True, slots=True)
class Event:
    """Representasi pertandingan yang sudah disederhanakan dari response mentah."""

    id: str
    name: str
    league: str | None
    home_team: str | None
    away_team: str | None
    date: str | None  # format "YYYY-MM-DD" sesuai response API
    time: str | None  # format "HH:MM:SS" UTC sesuai response API
    venue: str | None

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> "Event":
        return cls(
            id=raw["idEvent"],
            name=raw.get("strEvent", "Unknown Event"),
            league=raw.get("strLeague"),
            home_team=raw.get("strHomeTeam"),
            away_team=raw.get("strAwayTeam"),
            date=raw.get("dateEvent"),
            time=raw.get("strTime"),
            venue=raw.get("strVenue"),
        )

    @property
    def kickoff_utc(self) -> datetime | None:
        """Gabungkan date + time jadi objek datetime UTC. None kalau data tidak lengkap."""
        if not self.date or not self.time:
            return None
        try:
            return datetime.strptime(f"{self.date} {self.time}", "%Y-%m-%d %H:%M:%S")
        except ValueError:
            logger.warning("Format tanggal/waktu tidak dikenali untuk event %s", self.id)
            return None


class TheSportsDBClient:
    """
    Client tipis di atas TheSportsDB REST API (free tier).

    Pakai instance ini lewat dependency injection ke service lain, jangan
    buat instance baru di banyak tempat, supaya `requests.Session` bisa
    dipakai ulang (connection pooling) dan mocking di test lebih mudah.
    """

    def __init__(
        self,
        api_key: str = FREE_TEST_API_KEY,
        session: requests.Session | None = None,
        timeout: int = DEFAULT_TIMEOUT_SECONDS,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ) -> None:
        self._api_key = api_key
        self._session = session or requests.Session()
        self._timeout = timeout
        self._max_retries = max_retries

    def search_team(self, team_name: str) -> Team:
        """Cari tim berdasarkan nama. Melempar TeamNotFoundError kalau tidak ketemu."""
        data = self._get("searchteams.php", params={"t": team_name})
        teams = data.get("teams")
        if not teams:
            raise TeamNotFoundError(f"Tim '{team_name}' tidak ditemukan di TheSportsDB")
        return Team.from_raw(teams[0])

    def get_next_event_for_team(self, team_id: str) -> Event | None:
        """
        Ambil pertandingan berikutnya untuk sebuah tim.

        Catatan tier gratis: hanya mengembalikan event kandang (home) dan
        maksimal 1 hasil. Return None kalau memang belum ada jadwal berikutnya.
        """
        data = self._get("eventsnext.php", params={"id": team_id})
        events = data.get("events")
        if not events:
            return None
        return Event.from_raw(events[0])

    def get_last_event_for_team(self, team_id: str) -> Event | None:
        """Ambil pertandingan terakhir yang sudah selesai untuk sebuah tim."""
        data = self._get("eventslast.php", params={"id": team_id})
        events = data.get("results")
        if not events:
            return None
        return Event.from_raw(events[0])

    def _get(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        """
        Wrapper request HTTP dengan retry sederhana untuk rate limit (429).

        Retry dibatasi `max_retries` supaya scheduler loop tidak nyangkut
        lama kalau API sedang bermasalah.
        """
        url = f"{BASE_URL}/{self._api_key}/{endpoint}"
        last_error: Exception | None = None

        for attempt in range(1, self._max_retries + 2):
            try:
                response = self._session.get(url, params=params, timeout=self._timeout)
            except requests.RequestException as exc:
                last_error = exc
                logger.warning(
                    "Percobaan %s/%s gagal untuk %s: %s",
                    attempt, self._max_retries + 1, endpoint, exc,
                )
                continue

            if response.status_code == RATE_LIMIT_STATUS_CODE:
                logger.warning(
                    "Kena rate limit TheSportsDB di %s, tunggu %ss sebelum retry",
                    endpoint, RATE_LIMIT_BACKOFF_SECONDS,
                )
                if attempt <= self._max_retries:
                    time.sleep(RATE_LIMIT_BACKOFF_SECONDS)
                    continue
                raise RateLimitExceededError(
                    f"Rate limit TheSportsDB terlampaui saat memanggil {endpoint}"
                )

            if response.status_code != 200:
                raise SportsAPIError(
                    f"TheSportsDB mengembalikan status {response.status_code} untuk {endpoint}"
                )

            try:
                return response.json()
            except ValueError as exc:
                raise SportsAPIError(f"Response {endpoint} bukan JSON valid") from exc

        raise SportsAPIError(
            f"Gagal memanggil {endpoint} setelah {self._max_retries + 1} percobaan"
        ) from last_error

    def close(self) -> None:
        """Tutup session. Panggil saat bot shutdown."""
        self._session.close()