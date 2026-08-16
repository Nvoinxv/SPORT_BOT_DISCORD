import discord
from discord.ext import commands
from bot.config import DISCORD_TOKEN
from utils.logger import logger
from db.database import db

class SportBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="!",
            intents=discord.Intents.default(),
            help_command=None
        )

    async def setup_hook(self):
        # Connect to MongoDB
        await db.connect()
        
        # Load cogs
        cogs = ["cogs.admin", "cogs.reminders"]
        for cog in cogs:
            try:
                await self.load_extension(cog)
                logger.info(f"Loaded cog: {cog}")
            except Exception as e:
                logger.error(f"Failed to load cog {cog}: {e}")

        # Sync app commands (slash commands)
        try:
            await self.tree.sync()
            logger.info("Synced slash commands globally.")
        except Exception as e:
            logger.error(f"Failed to sync slash commands: {e}")

    async def on_ready(self):
        logger.info(f"Bot is ready! Logged in as {self.user} (ID: {self.user.id})")

def main():
    bot = SportBot()
    bot.run(DISCORD_TOKEN)

if __name__ == "__main__":
    main()
