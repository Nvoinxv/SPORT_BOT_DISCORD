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
    @app_commands.checks.has_permissions(administrator=True)
    async def trigger_news(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            "⏳ Memproses... Bot sedang mengambil berita olahraga, tunggu sebentar ya!",
            ephemeral=True
        )
        await self.scheduler.notifier.check_and_notify(is_startup=False)
        await interaction.edit_original_response(
            content="✅ Berita olahraga sudah dikirim ke channel!"
        )


async def setup(bot):
    await bot.add_cog(AdminCog(bot))
