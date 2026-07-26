from discord.ext import tasks
from services.notifier import NotifierService
from utils.logger import logger

class ReminderLoop:
    def __init__(self, bot):
        self.bot = bot
        self.notifier = NotifierService(bot)
        self.check_matches.start()

    @tasks.loop(hours=24)
    async def check_matches(self):
        logger.info("Scheduler Triggered: Checking for matches...")
        await self.notifier.check_and_notify()
        
    @check_matches.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()
        logger.info("Scheduler is ready and waiting for loops.")
