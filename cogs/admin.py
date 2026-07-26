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

async def setup(bot):
    await bot.add_cog(AdminCog(bot))
