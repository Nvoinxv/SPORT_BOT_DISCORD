# services/content_service.py
from __future__ import annotations

import datetime
import random
from dataclasses import dataclass
from typing import Literal

from services.gemini_service import GeminiService
from services.sports_api import TheSportsDBClient, AUTO_SOURCES, SportsAPIError
from utils.logger import logger

Category = Literal["branded_shoes", "sport_shoes", "sport_random", "health_edu"]

WITA_TZ = datetime.timezone(datetime.timedelta(hours=8))

# Liga yang erat kaitannya dengan sepatu (untuk kategori sport+shoes)
SHOE_RELATED_LEAGUES = [
    {"name": "NBA", "sport": "Basketball", "league_id": "4387"},          # sepatu basket
    {"name": "ATP Tour", "sport": "Tennis", "league_id": "4424"},         # sepatu tenis
    # Tambahkan kalau TheSportsDB support:
    # {"name": "Bundesliga", "sport": "Soccer", "league_id": "4331"},     # sepatu bola
]

@dataclass(frozen=True, slots=True)
class ContentItem:
    category: Category
    title: str
    body: str
    image_url: str | None = None
    source: str = "gemini"  # atau "thesportsdb"


class ContentService:
    """
    Orchestrator konten harian.
    Menentukan kategori berdasarkan JAM (WITA), lalu generate/fetch konten.
    """

    def __init__(
        self,
        gemini: GeminiService | None = None,
        sports_client: TheSportsDBClient | None = None,
    ) -> None:
        self.gemini = gemini or GeminiService()
        self.sports = sports_client or TheSportsDBClient()

    # -----------------------------------------------------------------
    # Dispatcher berdasarkan jam WITA
    # -----------------------------------------------------------------
    async def get_content_for_hour(self, hour: int | None = None) -> ContentItem:
        """
        hour: 0-23 WITA. None = jam sekarang.
        Mapping:
          10 -> branded_shoes   (Sepatu Branded)
          11 -> sport_shoes     (Sport + Sepatu)
          12 -> sport_random    (Sport Random)
          13 -> health_edu      (Edukasi Kesehatan)
        """
        if hour is None:
            hour = datetime.datetime.now(WITA_TZ).hour

        # Normalisasi: kalau di luar range, fallback ke slot
        slot = self._hour_to_slot(hour)

        match slot:
            case 0:
                return await self._generate_branded_shoes()
            case 1:
                return await self._generate_sport_shoes()
            case 2:
                return await self._generate_sport_random()
            case 3:
                return await self._generate_health_edu()
            case _:
                # Fallback: sport random
                return await self._generate_sport_random()

    def _hour_to_slot(self, hour: int) -> int:
        """Map jam ke slot 0-3. Hanya aktif 10-13 WITA, selain itu random."""
        mapping = {10: 0, 11: 1, 12: 2, 13: 3}
        return mapping.get(hour, random.randint(0, 3))

    # -----------------------------------------------------------------
    # 1. SEPATU BRANDED (Prioritas utama)
    # -----------------------------------------------------------------
    async def _generate_branded_shoes(self) -> ContentItem:
        """Generate konten sepatu branded China (Li-Ning, Anta) via Gemini."""
        if not self.gemini.is_ready:
            return ContentItem(
                category="branded_shoes",
                title="👟 Info Sepatu Branded",
                body="*(Fitur AI sedang dinonaktifkan)*",
            )

        brands = ["Li-Ning", "Anta", "Li-Ning dan Anta"]
        chosen = random.choice(brands)

        prompt = (
            f"Kamu adalah influencer sneakers yang update dengan tren global. "
            f"Buat 1 postingan menarik (maksimal 5 kalimat) tentang sepatu sport branded China, "
            f"khususnya **{chosen}**. Bisa tentang: sejarah brand, teknologi terbaru, "
            f"kolaborasi dengan atlet (contoh: Klay Thompson x Anta, Jimmy Butler x Li-Ning), "
            f"atau kenapa brand ini naik daun. Gunakan bahasa Indonesia yang asik, gaul tapi tetap informatif. "
            f"Tambahkan emoji yang pas. Jangan terlalu panjang, cocok untuk Discord."
        )

        try:
            body = await self.gemini.generate_raw(prompt)
            return ContentItem(
                category="branded_shoes",
                title=f"🔥 Sneakers Corner: {chosen}",
                body=body,
                source="gemini",
            )
        except Exception as e:
            logger.error(f"Gagal generate branded shoes: {e}")
            return ContentItem(
                category="branded_shoes",
                title="👟 Sneakers Corner",
                body="*(Gagal memuat info sepatu branded hari ini)*",
            )

    # -----------------------------------------------------------------
    # 2. SPORT YANG BERHUBUNGAN DENGAN SEPATU
    # -----------------------------------------------------------------
    async def _generate_sport_shoes(self) -> ContentItem:
        """
        Kombinasi: ambil pertandingan dari liga shoe-related (NBA/ATP),
        lalu generate ringkasan + sentuhan edukasi sepatu.
        """
        if not self.sports:
            return await self._fallback_sport_shoes_gemini()

        league = random.choice(SHOE_RELATED_LEAGUES)
        try:
            events = self.sports.get_latest_events_for_league(league["league_id"])
            if not events:
                return await self._fallback_sport_shoes_gemini()

            event = random.choice(events)
            # Generate via Gemini dengan angle "sepatu"
            body = await self.gemini.generate_sport_shoes_angle(
                sport=league["sport"],
                league=league["name"],
                home_team=event.home_team or "Tim A",
                away_team=event.away_team or "Tim B",
                home_score=event.home_score,
                away_score=event.away_score,
            )
            return ContentItem(
                category="sport_shoes",
                title=f"🏀⚽ {league['name']} & Sneakers",
                body=body,
                image_url=event.thumb_url,
                source="thesportsdb+gemini",
            )
        except SportsAPIError as e:
            logger.warning(f"TheSportsDB gagal untuk sport_shoes: {e}")
            return await self._fallback_sport_shoes_gemini()

    async def _fallback_sport_shoes_gemini(self) -> ContentItem:
        """Fallback kalau TheSportsDB error: pure Gemini edukasi sepatu olahraga."""
        topics = [
            "Cara memilih sepatu basket yang tepat",
            "Teknologi cushioning terbaru di sepatu lari",
            "Bedanya sepatu tenis dan sepatu badminton",
            "Mengapa NBA players pilih brand tertentu",
        ]
        topic = random.choice(topics)

        prompt = (
            f"Jelaskan '{topic}' dalam 4-5 kalimat bahasa Indonesia yang santai dan mudah dipahami. "
            f"Gunakan gaya ngobrol di Discord, tambahkan emoji. Fokus pada edukasi ringan."
        )
        body = await self.gemini.generate_raw(prompt)
        return ContentItem(
            category="sport_shoes",
            title=f"👟 Edukasi: {topic}",
            body=body,
            source="gemini",
        )

    # -----------------------------------------------------------------
    # 3. SPORT RANDOM
    # -----------------------------------------------------------------
    async def _generate_sport_random(self) -> ContentItem:
        """Ambil pertandingan random dari AUTO_SOURCES yang sudah ada."""
        if not self.sports:
            return ContentItem(
                category="sport_random",
                title="🏆 Sport Update",
                body="*(Sports API tidak tersedia)*",
            )

        source = random.choice(AUTO_SOURCES)
        try:
            events = self.sports.get_latest_events_for_league(source["league_id"])
            if not events:
                return ContentItem(
                    category="sport_random",
                    title="🏆 Sport Update",
                    body="*(Belum ada pertandingan terbaru)*",
                )

            event = random.choice(events)
            # Bisa pakai Gemini untuk ringkas, atau format manual
            body = (
                f"🏆 **{event.name}**\n"
                f"⚔️ {event.home_team} vs {event.away_team}\n"
                f"📊 Skor: {event.home_score or '-'} - {event.away_score or '-'}\n"
                f"📅 {event.date or 'Tanggal tidak tersedia'}"
            )
            return ContentItem(
                category="sport_random",
                title=f"📰 {source['name']} Update",
                body=body,
                image_url=event.thumb_url,
                source="thesportsdb",
            )
        except SportsAPIError as e:
            logger.error(f"Sport random error: {e}")
            return ContentItem(
                category="sport_random",
                title="🏆 Sport Update",
                body="*(Gagal mengambil data pertandingan)*",
            )

    # -----------------------------------------------------------------
    # 4. EDUKASI KESEHATAN
    # -----------------------------------------------------------------
    async def _generate_health_edu(self) -> ContentItem:
        """Generate tips kesehatan olahraga via Gemini."""
        if not self.gemini.is_ready:
            return ContentItem(
                category="health_edu",
                title="💡 Health Tips",
                body="*(Fitur AI sedang dinonaktifkan)*",
            )

        topics = [
            "Tips pemanasan sebelum olahraga agar tidak cedera",
            "Nutrisi terbaik setelah workout",
            "Cara recovery cepat setelah basket/sepakbola",
            "Mengapa istirahat cukup penting untuk atlet",
            "Cara merawat kaki setelah lari marathon",
            "Bedanya dehydration dan overhydration saat olahraga",
        ]
        topic = random.choice(topics)

        prompt = (
            f"Kamu adalah trainer olahraga yang friendly. "
            f"Buat tips singkat (4-5 kalimat) tentang: **{topic}**. "
            f"Bahasa Indonesia santai, jangan kaku, tambahkan emoji yang relevan. "
            f"Fokus pada edukasi praktis yang bisa langsung diterapkan."
        )

        try:
            body = await self.gemini.generate_raw(prompt)
            return ContentItem(
                category="health_edu",
                title=f"💡 Health Tips: {topic}",
                body=body,
                source="gemini",
            )
        except Exception as e:
            logger.error(f"Health edu error: {e}")
            return ContentItem(
                category="health_edu",
                title="💡 Health Tips",
                body="*(Gagal memuat tips kesehatan hari ini)*",
            )