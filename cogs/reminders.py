"""
RemindersCog — Slash commands yang tersedia untuk user.

Karena bot kini berjalan dalam mode otomatis penuh, cog ini
hanya menyediakan command informasional yang berguna untuk user,
bukan perintah untuk mendaftarkan tim.

Slash command yang tersedia:
- /team_search : Mencari info dan ringkasan AI tentang sebuah tim.
- /team_next   : Melihat jadwal kandang terdekat dari sebuah tim.
"""

import discord
from discord import app_commands
from discord.ext import commands
import asyncio
from services.sports_api import TheSportsDBClient, TeamNotFoundError, SportsAPIError
from utils.logger import logger
from services.gemini_service import GeminiService


class RemindersCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.api = TheSportsDBClient()
        self.ai = GeminiService()

    @app_commands.command(name="team_search", description="Mencari informasi dan ringkasan AI tentang tim olahraga.")
    @app_commands.describe(team_name="Nama tim yang dicari")
    async def team_search(self, interaction: discord.Interaction, team_name: str):
        await interaction.response.defer()
        try:
            team = await asyncio.to_thread(self.api.search_team, team_name)
            
            ai_summary = await self.ai.get_team_summary(
                team_name=team.name, 
                sport=team.sport, 
                league=team.league
            )
            
            embed = discord.Embed(title=team.name, color=0x3498DB)
            embed.add_field(name="ID Tim", value=team.id, inline=True)
            if team.league:
                embed.add_field(name="Liga", value=team.league, inline=True)
            if team.sport:
                embed.add_field(name="Olahraga", value=team.sport, inline=True)
            embed.add_field(name="🤖 Ringkasan AI", value=ai_summary, inline=False)
            
            await interaction.followup.send(embed=embed)
        except TeamNotFoundError:
            await interaction.followup.send(f"Tim '{team_name}' tidak ditemukan.", ephemeral=True)
        except SportsAPIError as e:
            await interaction.followup.send(f"Terjadi kesalahan saat menghubungi API: {e}", ephemeral=True)

    @app_commands.command(name="team_next", description="Melihat pertandingan kandang selanjutnya dari sebuah tim.")
    @app_commands.describe(team_name="Nama tim")
    async def team_next(self, interaction: discord.Interaction, team_name: str):
        await interaction.response.defer()
        try:
            team = await asyncio.to_thread(self.api.search_team, team_name)
            event = await asyncio.to_thread(self.api.get_next_event_for_team, team.id)
            
            if not event:
                await interaction.followup.send(f"Belum ada jadwal kandang terdekat untuk **{team.name}**.")
                return

            embed = discord.Embed(title="Pertandingan Selanjutnya", description=f"**{event.name}**", color=0x2ECC71)
            embed.add_field(name="Tanggal", value=event.date, inline=True)
            embed.add_field(name="Waktu (UTC)", value=event.time, inline=True)
            if event.venue:
                embed.add_field(name="Stadium", value=event.venue, inline=False)
            await interaction.followup.send(embed=embed)
        except TeamNotFoundError:
            await interaction.followup.send(f"Tim '{team_name}' tidak ditemukan.", ephemeral=True)
        except SportsAPIError as e:
            await interaction.followup.send(f"Terjadi kesalahan saat menghubungi API: {e}", ephemeral=True)


async def setup(bot):
    await bot.add_cog(RemindersCog(bot))
