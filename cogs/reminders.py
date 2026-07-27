import discord
from discord import app_commands
from discord.ext import commands
import asyncio
from services.sports_api import TheSportsDBClient, TeamNotFoundError, SportsAPIError
from db.repository import SubscriptionRepository
from db.models import Subscription
from utils.logger import logger
from services.gemini_service import GeminiService

class RemindersCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.api = TheSportsDBClient()
        self.repo = SubscriptionRepository()
        self.ai = GeminiService()

    @app_commands.command(name="team_search", description="Mencari informasi dan ringkasan AI tentang tim olahraga.")
    @app_commands.describe(team_name="Nama tim yang dicari")
    async def team_search(self, interaction: discord.Interaction, team_name: str):
        await interaction.response.defer()
        try:
            team = await asyncio.to_thread(self.api.search_team, team_name)
            
            # Memanggil Gemini AI untuk merangkum data tim
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
                
            # Menambahkan field khusus ringkasan AI
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

    @app_commands.command(name="subscribe", description="Mendaftarkan channel ini untuk menerima pengingat jadwal tim.")
    @app_commands.describe(team_name="Nama tim")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def subscribe(self, interaction: discord.Interaction, team_name: str):
        await interaction.response.defer()
        try:
            team = await asyncio.to_thread(self.api.search_team, team_name)
            sub = Subscription(
                channel_id=interaction.channel_id,
                team_id=team.id,
                team_name=team.name,
                guild_id=interaction.guild_id
            )
            success = await self.repo.add_subscription(sub)
            if success:
                embed = discord.Embed(
                    title="Berhasil Berlangganan",
                    description=f"Channel ini akan menerima pengingat otomatis untuk **{team.name}**.",
                    color=0x2ECC71
                )
                await interaction.followup.send(embed=embed)
            else:
                await interaction.followup.send(f"Channel ini sudah berlangganan pengingat untuk **{team.name}**.", ephemeral=True)
        except TeamNotFoundError:
            await interaction.followup.send(f"Tim '{team_name}' tidak ditemukan.", ephemeral=True)
        except Exception as e:
            logger.error(f"Subscription error: {e}")
            await interaction.followup.send("Gagal berlangganan karena masalah internal.", ephemeral=True)

    @app_commands.command(name="trigger_notification", description="Secara manual mengecek dan mengirim notifikasi pertandingan (hanya Admin).")
    @app_commands.checks.has_permissions(administrator=True)
    async def trigger_notification(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        admin_cog = self.bot.get_cog("AdminCog")
        if admin_cog and hasattr(admin_cog, "scheduler"):
            # Trigger notifier secara asinkron (di-await) agar kita tahu saat selesai
            await admin_cog.scheduler.notifier.check_and_notify()
            await interaction.followup.send("✅ Pengecekan manual selesai. Notifikasi telah dikirim ke channel yang sesuai jika ada jadwal yang cocok.")
        else:
            await interaction.followup.send("❌ Gagal menemukan layanan Notifier/Scheduler yang berjalan.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(RemindersCog(bot))
