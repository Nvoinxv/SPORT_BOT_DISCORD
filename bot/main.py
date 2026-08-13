import asyncio
import logging
import discord
from discord.ext import commands
import aiohttp

# 1. Konfigurasi Logging yang proper
logging.basicConfig(
    level=logging.INFO,
    format='[{asctime}] [{levelname:<8}] {name}: {message}',
    style='{',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('discord')

class ProductionBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix='!',
            intents=discord.Intents.default(), # Sesuaikan dengan kebutuhan
            # Mengurangi load saat startup jika bot masuk di banyak server
            chunk_guilds_at_startup=False 
        )
        # Sediakan aiohttp session global yang bisa dipakai di seluruh Cogs
        self.session: aiohttp.ClientSession | None = None

    async def setup_hook(self):
        """Dipanggil sekali saat bot mulai. Tempat terbaik untuk setup koneksi async."""
        self.session = aiohttp.ClientSession()
        logger.info("Global aiohttp session created.")
        
        # Load cogs kamu di sini
        # await self.load_extension("cogs.music")
        # await self.load_extension("cogs.admin")

    async def close(self):
        """Dipanggil saat bot dimatikan. Mencegah error 'Unclosed connection'."""
        if self.session:
            await self.session.close()
            logger.info("Global aiohttp session closed.")
        await super().close()

    async def on_ready(self):
        logger.info(f"Bot Ready! Logged in as {self.user} (ID: {self.user.id})")


async def main():
    # 2. SETUP MONITORING EVENT LOOP (Penting!)
    loop = asyncio.get_running_loop()
    loop.set_debug(True)
    # Jika ada kode yang memblokir loop lebih dari 0.5 detik, akan dicetak ke log!
    loop.slow_callback_duration = 0.5 

    bot = ProductionBot()
    token = "TOKEN_DISCORD_KAMU" # Ganti pakai os.getenv() / dotenv
    
    # 3. Graceful runner
    async with bot:
        await bot.start(token)

if __name__ == "__main__":
    try:
        # Menggunakan asyncio.run() menggantikan bot.run()
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot manually shut down.")