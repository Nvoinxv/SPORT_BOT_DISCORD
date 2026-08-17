"""
AdminCog — Perintah utilitas untuk admin server.

Slash command yang tersedia:
- /ping     : Mengecek status dan latensi bot.
- /trigger_news : (Admin only) Paksa bot kirim berita sekarang tanpa menunggu scheduler.
"""

import discord
from discord.ext import commands
from discord import app_commands
from scheduler.loop import ReminderLoop


class AdminCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Start the scheduler loop when admin cog loads
        self.scheduler = ReminderLoop(self.bot)

    async def cog_unload(self):
        """Dipanggil saat cog di-unload atau bot dimatikan untuk mencegah Unclosed Connection."""
        self.scheduler.daily_news.cancel()
        if hasattr(self.scheduler.content_service, 'close'):
            self.scheduler.content_service.close()

    @app_commands.command(name="ping", description="Mengecek status dan latensi bot.")
    async def ping(self, interaction: discord.Interaction):
        latency = round(self.bot.latency * 1000)
        embed = discord.Embed(
            title="Status Bot",
            description=f"Bot aktif dan berjalan normal.\n**Latensi:** {latency}ms",
            color=0x9B59B6
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="trigger_news",
        description="[Admin] Paksa bot kirim ringkasan berita olahraga sekarang ke channel."
    )
    @app_commands.describe(tipe="Pilih tipe testing")
    @app_commands.choices(tipe=[
        app_commands.Choice(name="Berdasarkan Jam / Random", value="auto"),
        app_commands.Choice(name="Kirim SEMUA Kategori (Test 4 Topik)", value="all"),
        app_commands.Choice(name="1. Sepatu Branded", value="0"),
        app_commands.Choice(name="2. Sport + Sepatu", value="1"),
        app_commands.Choice(name="3. Sport Random", value="2"),
        app_commands.Choice(name="4. Edukasi Kesehatan", value="3"),
    ])
    @app_commands.checks.has_permissions(administrator=True)
    async def trigger_news(self, interaction: discord.Interaction, tipe: str = "auto"):
        await interaction.response.send_message(
            "⏳ Memproses... Bot sedang mengambil konten, tunggu sebentar ya!",
            ephemeral=True
        )
        if tipe == "all":
            for i in range(4):
                content = await self.scheduler.content_service.get_content_for_slot(i)
                await self.scheduler.notifier.send_content(content)
            await interaction.edit_original_response(content="✅ Ke-4 kategori berita sudah dikirim ke channel!")
        elif tipe in ["0", "1", "2", "3"]:
            content = await self.scheduler.content_service.get_content_for_slot(int(tipe))
            await self.scheduler.notifier.send_content(content)
            await interaction.edit_original_response(content=f"✅ Kategori {tipe} sudah dikirim ke channel!")
        else:
            import datetime
            now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
            content = await self.scheduler.content_service.get_content_for_hour(now.hour)
            await self.scheduler.notifier.send_content(content)
            await interaction.edit_original_response(
                content="✅ Berita (auto) sudah dikirim ke channel!"
            )


async def setup(bot):
    await bot.add_cog(AdminCog(bot))
