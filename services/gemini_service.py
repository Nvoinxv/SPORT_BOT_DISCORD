import google.generativeai as genai
from bot.config import GEMINI_API_KEY
from utils.logger import logger
import asyncio

class GeminiService:
    def __init__(self):
        self.is_ready = False
        if GEMINI_API_KEY:
            try:
                genai.configure(api_key=GEMINI_API_KEY)
                self.model = genai.GenerativeModel('gemini-3.5-flash')
                self.is_ready = True
                logger.info("Gemini AI is ready.")
            except Exception as e:
                logger.error(f"Failed to initialize Gemini AI: {e}")
        else:
            logger.warning("GEMINI_API_KEY is not set. AI features will be disabled.")

    async def get_team_summary(self, team_name: str, sport: str, league: str) -> str:
        if not self.is_ready:
            return "*(Fitur ringkasan AI sedang dinonaktifkan karena API Key tidak tersedia)*"
        
        prompt = (
            f"Berikan ringkasan singkat (maksimal 2-3 kalimat) mengenai tim {sport or 'olahraga'} "
            f"bernama {team_name} yang bermain di liga {league or 'profesional'}. "
            "Gunakan bahasa Indonesia yang asik, jelas, padat, dan mudah dipahami anak-anak Discord. "
            "Jangan gunakan terlalu banyak emoji, hindari bahasa robot/kaku, jangan bertele-tele."
        )
        
        try:
            response = await asyncio.to_thread(self.model.generate_content, prompt)
            return response.text.strip()
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            return "*(Gagal mendapatkan ringkasan AI untuk saat ini)*"

    async def get_event_news_summary(
        self,
        sport: str,
        league: str,
        home_team: str,
        away_team: str,
        home_score: str | None,
        away_score: str | None,
        date: str | None,
        venue: str | None,
    ) -> str:
        """
        Menghasilkan ringkasan berita olahraga bergaya reporter dari data pertandingan.
        Digunakan untuk mode loop otomatis bot.
        """
        if not self.is_ready:
            return "*(Ringkasan AI tidak tersedia karena API Key tidak dikonfigurasi)*"

        # Siapkan info skor
        if home_score is not None and away_score is not None:
            score_info = f"Skor akhir: {home_team} {home_score} - {away_score} {away_team}."
            match_status = "pertandingan yang baru selesai"
        else:
            score_info = "Skor belum tersedia."
            match_status = "pertandingan terkini"

        venue_info = f"Bertempat di {venue}." if venue else ""
        date_info = f"Dimainkan pada {date}." if date else ""

        prompt = (
            f"Kamu adalah reporter olahraga Discord yang seru dan asik. "
            f"Buat ringkasan berita singkat (3-4 kalimat) tentang {match_status} berikut:\n\n"
            f"🏆 Liga: {league} ({sport})\n"
            f"⚔️ {home_team} vs {away_team}\n"
            f"📅 {date_info} {venue_info}\n"
            f"📊 {score_info}\n\n"
            "Gunakan bahasa Indonesia yang casual, seru, dan tidak kaku. "
            "Tulis layaknya berita pendek yang menarik untuk dibaca di Discord. "
            "Boleh ada sedikit komentar atau analisis ringan tentang performa tim. "
            "Jangan melebih-lebihkan dan jangan terlalu formal."
        )

        try:
            response = await asyncio.to_thread(self.model.generate_content, prompt)
            return response.text.strip()
        except Exception as e:
            logger.error(f"Gemini API error (event news): {e}")
            return "*(Gagal mendapatkan ringkasan AI untuk pertandingan ini)*"

    async def generate_raw(self, prompt: str) -> str:
        """Generate teks bebas dari prompt apa pun."""
        if not self.is_ready:
            return "*(Fitur AI sedang dinonaktifkan)*"
        try:
            response = await asyncio.to_thread(self.model.generate_content, prompt)
            return response.text.strip()
        except Exception as e:
            logger.error(f"Gemini raw error: {e}")
            return "*(Gagal generate konten AI)*"

    async def generate_sport_shoes_angle(
        self,
        sport: str,
        league: str,
        home_team: str,
        away_team: str,
        home_score: str | None,
        away_score: str | None,
    ) -> str:
        """
        Generate ringkasan pertandingan dengan angle "sepatu/sneakers".
        """
        if not self.is_ready:
            return "*(Ringkasan AI tidak tersedia)*"

        score_info = f"Skor: {home_team} {home_score or '-'} - {away_score or '-'} {away_team}" if home_score and away_score else "Skor belum tersedia."

        prompt = (
            f"Kamu adalah reporter olahraga yang juga sneakerhead. "
            f"Buat ringkasan singkat (3-4 kalimat) pertandingan {sport} di {league}: "
            f"{home_team} vs {away_team}. {score_info}\n\n"
            f"Selain hasil pertandingan, tambahkan 1 kalimat ringan tentang "
            f"sepatu yang biasa dipakai pemain di liga ini atau brand yang mensponsori. "
            f"Bahasa Indonesia casual, asik, cocok untuk Discord. Jangan panjang-panjang."
        )
        try:
            response = await asyncio.to_thread(self.model.generate_content, prompt)
            return response.text.strip()
        except Exception as e:
            logger.error(f"Gemini sport+shoes error: {e}")
            return "*(Gagal mendapatkan ringkasan)*"