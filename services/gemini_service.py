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
                self.model = genai.GenerativeModel('gemini-1.5-flash')
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
            # Generate content in a thread to avoid blocking the event loop
            response = await asyncio.to_thread(self.model.generate_content, prompt)
            return response.text.strip()
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            return "*(Gagal mendapatkan ringkasan AI untuk saat ini)*"
