# services/content_service.py
from __future__ import annotations

import datetime
import random
from dataclasses import dataclass
from typing import Literal

from services.gemini_service import GeminiService
from services.news_api import GNewsClient, NewsAPIError, NewsAPIKeyMissingError
from services.newsdata_api import NewsDataClient, NewsDataAPIError, NewsDataAPIKeyMissingError
from services.sports_api import TheSportsDBClient, AUTO_SOURCES, SportsAPIError
from utils.logger import logger
from db.models import ContentLog  # untuk membuat log object
from db.repository import ContentLogRepository, DailyStatsRepository, ChannelConfigRepository

Category = Literal["branded_shoes", "sport_shoes", "sport_random", "health_edu"]

WITA_TZ = datetime.timezone(datetime.timedelta(hours=8))

# Gambar fallback resolusi tinggi jika API berita / sports tidak menyediakan foto
DEFAULT_IMAGES: dict[str, str] = {
    "branded_shoes": "https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=800&q=80",
    "sport_shoes": "https://images.unsplash.com/photo-1579338559194-a162d19bf842?w=800&q=80",
    "sport_random": "https://images.unsplash.com/photo-1508098682722-e99c43a406b2?w=800&q=80",
    "health_edu": "https://images.unsplash.com/photo-1517838277536-f5f99be501cd?w=800&q=80",
}

# Liga yang erat kaitannya dengan sepatu (untuk kategori sport+shoes)
SHOE_RELATED_LEAGUES = [
    {"name": "NBA", "sport": "Basketball", "league_id": "4387"},
    {"name": "ATP Tour", "sport": "Tennis", "league_id": "4424"},
]

@dataclass(frozen=True, slots=True)
class ContentItem:
    category: Category
    title: str
    body: str
    image_url: str | None = None
    source: str = "gemini"
    article_url: str | None = None


class ContentService:
    """
    Orchestrator konten harian.
    Menentukan kategori berdasarkan JAM (WITA), lalu generate/fetch konten.
    """

    def __init__(
        self,
        gemini: GeminiService | None = None,
        sports_client: TheSportsDBClient | None = None,
        gnews_client: GNewsClient | None = None,
        newsdata_client: NewsDataClient | None = None,
    ) -> None:
        self.gemini = gemini or GeminiService()
        self.sports = sports_client or TheSportsDBClient()
        self.gnews = gnews_client or GNewsClient()
        self.newsdata = newsdata_client or NewsDataClient()
        
        # Repository baru untuk tracking
        self.log_repo = ContentLogRepository()
        self.stats_repo = DailyStatsRepository()
        self.channel_repo = ChannelConfigRepository()

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

        slot = self._hour_to_slot(hour)

        item: ContentItem
        match slot:
            case 0:
                item = await self._generate_branded_shoes()
            case 1:
                item = await self._generate_sport_shoes()
            case 2:
                item = await self._generate_sport_random()
            case 3:
                item = await self._generate_health_edu()
            case _:
                item = await self._generate_sport_random()

        # Pastikan gambar selalu ada (image_url tidak boleh None/kosong)
        if not item.image_url:
            fallback_img = DEFAULT_IMAGES.get(item.category, DEFAULT_IMAGES["sport_random"])
            item = ContentItem(
                category=item.category,
                title=item.title,
                body=item.body,
                image_url=fallback_img,
                source=item.source,
                article_url=item.article_url,
            )
        return item

    def _hour_to_slot(self, hour: int) -> int:
        """Map jam ke slot 0-3. Hanya aktif 10-13 WITA, selain itu random."""
        mapping = {10: 0, 11: 1, 12: 2, 13: 3}
        return mapping.get(hour, random.randint(0, 3))

    # -----------------------------------------------------------------
    # 1. SEPATU BRANDED (Prioritas utama) — GNEWS + Gemini
    # -----------------------------------------------------------------
    async def _generate_branded_shoes(self) -> ContentItem:
        """
        Strategi Hybrid:
        1. Cari berita REAL via GNews (Li-Ning / Anta / sneakers)
        2. Feed ke Gemini untuk diringkas & diterjemahkan ke bahasa Indonesia gaya Discord
        3. Kalau GNews gagal/tidak ada API key → fallback ke pure Gemini generate
        """
        brands = ["Li-Ning", "Anta", "Li-Ning dan Anta"]
        chosen_brand = random.choice(brands)

        # --- Step A: Coba ambil berita real dari GNews ---
        articles: list = []
        try:
            articles = self.gnews.search_sneakers(brand=chosen_brand, max_results=3)
        except (NewsAPIKeyMissingError, NewsAPIError) as e:
            logger.warning("GNews tidak tersedia untuk branded_shoes: %s", e)

        # --- Step B: Jika ada artikel, gabungkan & ringkas via Gemini ---
        if articles:
            context_parts = []
            for art in articles[:2]:
                context_parts.append(f"Judul: {art.title}\nDeskripsi: {art.description}")
            context = "\n\n".join(context_parts)

            prompt = (
                f"Kamu adalah influencer sneakers yang update dengan tren global. "
                f"Berikut adalah berita REAL dari internet tentang **{chosen_brand}**:\n\n"
                f"{context}\n\n"
                f"Tugas kamu:\n"
                f"1. Buat 1 postingan menarik (maksimal 5 kalimat) berdasarkan berita di atas.\n"
                f"2. Gunakan bahasa Indonesia yang asik, gaul tapi tetap informatif.\n"
                f"3. Tambahkan emoji yang pas. Jangan terlalu panjang, cocok untuk Discord.\n"
                f"4. Jangan copy-paste mentah, tapi ringkas dan ubah jadi gaya ngobrol.\n"
                f"5. Di akhir, tambahkan 1 kalimat ajakan diskusi ringan."
            )

            try:
                body = await self.gemini.generate_raw(prompt)
                image_url = articles[0].image
                article_url = articles[0].url
                return ContentItem(
                    category="branded_shoes",
                    title=f"🔥 Sneakers Corner: {chosen_brand}",
                    body=body,
                    image_url=image_url,
                    source="gnews+gemini",
                    article_url=article_url,
                )
            except Exception as e:
                logger.error("Gemini gagal ringkas GNews untuk branded_shoes: %s", e)
                art = articles[0]
                body = f"📰 **{art.title}**\n{art.description}\n🔗 {art.url}"
                return ContentItem(
                    category="branded_shoes",
                    title=f"🔥 Sneakers Corner: {chosen_brand}",
                    body=body,
                    image_url=art.image,
                    source="gnews_raw",
                    article_url=art.url,
                )

        # --- Step C: Fallback ke pure Gemini generate ---
        return await self._generate_branded_shoes_pure_gemini(chosen_brand)

    async def _generate_branded_shoes_pure_gemini(self, brand: str) -> ContentItem:
        """Generate sepatu branded tanpa data real (pure AI)."""
        if not self.gemini.is_ready:
            return ContentItem(
                category="branded_shoes",
                title="👟 Info Sepatu Branded",
                body="*(Fitur AI sedang dinonaktifkan)*",
            )

        prompt = (
            f"Kamu adalah influencer sneakers yang update dengan tren global. "
            f"Buat 1 postingan menarik (maksimal 5 kalimat) tentang sepatu sport branded China, "
            f"khususnya **{brand}**. Bisa tentang: sejarah brand, teknologi terbaru, "
            f"kolaborasi dengan atlet (contoh: Klay Thompson x Anta, Jimmy Butler x Li-Ning), "
            f"atau kenapa brand ini naik daun. Gunakan bahasa Indonesia yang asik, gaul tapi tetap informatif. "
            f"Tambahkan emoji yang pas. Jangan terlalu panjang, cocok untuk Discord."
        )

        try:
            body = await self.gemini.generate_raw(prompt)
            return ContentItem(
                category="branded_shoes",
                title=f"🔥 Sneakers Corner: {brand}",
                body=body,
                source="gemini",
            )
        except Exception as e:
            logger.error("Gagal generate branded shoes: %s", e)
            return ContentItem(
                category="branded_shoes",
                title="👟 Sneakers Corner",
                body="*(Gagal memuat info sepatu branded hari ini)*",
            )

    async def _save_log(self, content: ContentItem, channel_id: int) -> None:
        """Simpan log konten ke MongoDB."""
        try:
            log = ContentLog(
                category=content.category,
                title=content.title,
                body=content.body,
                source=content.source,
                article_url=content.article_url,
                image_url=content.image_url,
                channel_id=channel_id,
            )
            await self.log_repo.create(log)
            await self.stats_repo.increment(content.category)
        except Exception as e:
            logger.error("Gagal menyimpan log konten: %s", e)

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
            logger.warning("TheSportsDB gagal untuk sport_shoes: %s", e)
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

    async def _save_log(self, content: ContentItem, channel_id: int) -> None:
        """Simpan log konten ke MongoDB."""
        try:
            log = ContentLog(
                category=content.category,
                title=content.title,
                body=content.body,
                source=content.source,
                article_url=content.article_url,
                image_url=content.image_url,
                channel_id=channel_id,
            )
            await self.log_repo.create(log)
            await self.stats_repo.increment(content.category)
        except Exception as e:
            logger.error("Gagal menyimpan log konten: %s", e)

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
            logger.error("Sport random error: %s", e)
            return ContentItem(
                category="sport_random",
                title="🏆 Sport Update",
                body="*(Gagal mengambil data pertandingan)*",
            )

    async def _save_log(self, content: ContentItem, channel_id: int) -> None:
        """Simpan log konten ke MongoDB."""
        try:
            log = ContentLog(
                category=content.category,
                title=content.title,
                body=content.body,
                source=content.source,
                article_url=content.article_url,
                image_url=content.image_url,
                channel_id=channel_id,
            )
            await self.log_repo.create(log)
            await self.stats_repo.increment(content.category)
        except Exception as e:
            logger.error("Gagal menyimpan log konten: %s", e)

    # -----------------------------------------------------------------
    # 4. EDUKASI KESEHATAN — NEWSDATA.IO + Gemini
    # -----------------------------------------------------------------
    async def _generate_health_edu(self) -> ContentItem:
        """
        Strategi Hybrid:
        1. Cari berita kesehatan REAL via NewsData.io
        2. Ringkas & terjemahkan via Gemini ke bahasa Indonesia gaya Discord
        3. Fallback ke pure Gemini kalau NewsData.io gagal
        """
        topics = [
            "warm up before exercise injury prevention",
            "post workout nutrition recovery",
            "sleep recovery for athletes",
            "foot care after running marathon",
            "hydration exercise dehydration",
            "mental health exercise stress relief",
        ]
        chosen_topic = random.choice(topics)

        # --- Step A: Coba ambil berita real dari NewsData.io ---
        articles: list = []
        try:
            articles = self.newsdata.search_health(topic=chosen_topic, max_results=5)
        except (NewsDataAPIKeyMissingError, NewsDataAPIError) as e:
            logger.warning("NewsData.io tidak tersedia untuk health_edu: %s", e)

        # --- Step B: Jika ada artikel, ringkas via Gemini ---
        if articles:
            context_parts = []
            for art in articles[:2]:
                desc = art.description or "Tidak ada deskripsi."
                context_parts.append(f"Judul: {art.title}\nDeskripsi: {desc}")
            context = "\n\n".join(context_parts)

            prompt = (
                f"Kamu adalah trainer olahraga yang friendly. "
                f"Berikut adalah artikel kesehatan dari internet:\n\n"
                f"{context}\n\n"
                f"Tugas kamu:\n"
                f"1. Buat tips singkat (4-5 kalimat) berdasarkan artikel di atas.\n"
                f"2. Gunakan bahasa Indonesia santai, jangan kaku, tambahkan emoji relevan.\n"
                f"3. Fokus pada edukasi praktis yang bisa langsung diterapkan.\n"
                f"4. Jangan copy-paste mentah, ubah jadi gaya ngobrol di Discord.\n"
                f"5. Di akhir, tambahkan 1 pertanyaan ajak diskusi ringan."
            )

            try:
                body = await self.gemini.generate_raw(prompt)
                image_url = articles[0].image_url
                article_url = articles[0].url
                return ContentItem(
                    category="health_edu",
                    title="💡 Health Tips",
                    body=body,
                    image_url=image_url,
                    source="newsdata+gemini",
                    article_url=article_url,
                )
            except Exception as e:
                logger.error("Gemini gagal ringkas NewsData.io untuk health_edu: %s", e)
                art = articles[0]
                body = f"📰 **{art.title}**\n{art.description or 'Tidak ada deskripsi.'}\n🔗 {art.url}"
                return ContentItem(
                    category="health_edu",
                    title="💡 Health Tips",
                    body=body,
                    image_url=art.image_url,
                    source="newsdata_raw",
                    article_url=art.url,
                )

        # --- Step C: Fallback pure Gemini ---
        return await self._generate_health_edu_pure_gemini()

    async def _generate_health_edu_pure_gemini(self) -> ContentItem:
        """Generate tips kesehatan tanpa data real."""
        if not self.gemini.is_ready:
            return ContentItem(
                category="health_edu",
                title="💡 Health Tips",
                body="*(Fitur AI sedang dinonaktifkan)*",
            )

        topics_id = [
            "Tips pemanasan sebelum olahraga agar tidak cedera",
            "Nutrisi terbaik setelah workout",
            "Cara recovery cepat setelah basket/sepakbola",
            "Mengapa istirahat cukup penting untuk atlet",
            "Cara merawat kaki setelah lari marathon",
            "Bedanya dehydration dan overhydration saat olahraga",
            "Manfaat olahraga untuk kesehatan mental",
            "Cara mengatasi muscle soreness setelah gym",
        ]
        topic = random.choice(topics_id)

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
            logger.error("Health edu error: %s", e)
            return ContentItem(
                category="health_edu",
                title="💡 Health Tips",
                body="*(Gagal memuat tips kesehatan hari ini)*",
            )

    async def _save_log(self, content: ContentItem, channel_id: int) -> None:
        """Simpan log konten ke MongoDB."""
        try:
            log = ContentLog(
                category=content.category,
                title=content.title,
                body=content.body,
                source=content.source,
                article_url=content.article_url,
                image_url=content.image_url,
                channel_id=channel_id,
            )
            await self.log_repo.create(log)
            await self.stats_repo.increment(content.category)
        except Exception as e:
            logger.error("Gagal menyimpan log konten: %s", e)