import datetime
from discord.ext import tasks
from services.notifier import NotifierService
from utils.logger import logger

# WITA (Waktu Indonesia Tengah) adalah UTC+8
WITA_TZ = datetime.timezone(datetime.timedelta(hours=8))
SCHEDULE_TIME = datetime.time(hour=10, minute=0, tzinfo=WITA_TZ)


class ReminderLoop:
    def __init__(self, bot):
        self.bot = bot
        self.notifier = NotifierService(bot)
        self.daily_news.start()

    @tasks.loop(time=SCHEDULE_TIME)
    async def daily_news(self):
        """Dijalankan setiap hari pukul 10:00 WITA — kirim 1 berita olahraga acak."""
        logger.info("Scheduler dipicu: Mengirim berita olahraga harian...")
        await self.notifier.check_and_notify(is_startup=False)

    @daily_news.before_loop
    async def before_daily_news(self):
        """Tunggu bot siap, lalu langsung kirim berita pertama saat deploy."""
        await self.bot.wait_until_ready()
        logger.info("Bot siap. Mengirim berita olahraga pertama (startup)...")
        await self.notifier.check_and_notify(is_startup=True)
        logger.info("Berita startup selesai. Scheduler akan berjalan pukul 10:00 WITA setiap hari.")
