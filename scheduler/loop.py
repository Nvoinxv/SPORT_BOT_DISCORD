# scheduler/loop.py
import datetime
from discord.ext import tasks
from services.content_service import ContentService
from services.notifier import NotifierService  # asumsikan notifier punya method send_content
from utils.logger import logger

WITA_TZ = datetime.timezone(datetime.timedelta(hours=8))

# 4 slot waktu WITA
SCHEDULE_TIMES = [
    datetime.time(hour=10, minute=0, tzinfo=WITA_TZ),  # Sepatu Branded
    datetime.time(hour=11, minute=0, tzinfo=WITA_TZ),  # Sport + Sepatu
    datetime.time(hour=12, minute=0, tzinfo=WITA_TZ),  # Sport Random
    datetime.time(hour=13, minute=0, tzinfo=WITA_TZ),  # Edukasi Kesehatan
]


class ReminderLoop:
    def __init__(self, bot):
        self.bot = bot
        self.content_service = ContentService()
        self.notifier = NotifierService(bot)

    # ---------------------------------------------------------
    # Loop utama: dipicu 4x sehari
    # ---------------------------------------------------------
    @tasks.loop(time=SCHEDULE_TIMES)
    async def daily_news(self):
        now = datetime.datetime.now(WITA_TZ)
        hour = now.hour
        logger.info(f"Scheduler dipicu jam {hour}:00 WITA. Mengambil konten...")

        content = await self.content_service.get_content_for_hour(hour)
        await self.notifier.send_content(content)

    @daily_news.before_loop
    async def before_daily_news(self):
        await self.bot.wait_until_ready()
        logger.info("Bot siap. Scheduler aktif: 10-13 WITA setiap hari.")