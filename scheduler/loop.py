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
        self.check_matches.start()

    @tasks.loop(time=SCHEDULE_TIME)
    async def check_matches(self):
        logger.info("Scheduler Triggered: Checking for matches...")
        await self.notifier.check_and_notify()
        
    @check_matches.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()
        logger.info("Scheduler is ready and waiting for loops.")
        # Memicu output langsung saat bot pertama kali jalan (deploy)
        logger.info("Triggering initial check immediately on deploy...")
        await self.notifier.check_and_notify(is_startup=True)
