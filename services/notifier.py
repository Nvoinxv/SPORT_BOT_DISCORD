import asyncio
from datetime import datetime, timezone, timedelta
import discord
from db.repository import SubscriptionRepository
from services.sports_api import TheSportsDBClient
from utils.logger import logger

class NotifierService:
    def __init__(self, bot: discord.Client):
        self.bot = bot
        self.repo = SubscriptionRepository()
        self.api = TheSportsDBClient()

    async def check_and_notify(self, is_startup: bool = False):
        logger.info("Running check_and_notify task...")
        subs = await self.repo.get_all_subscriptions()
        
        if not subs:
            return

        # Group by team to avoid spamming the API
        teams_to_check = set(sub.team_id for sub in subs)
        
        for team_id in teams_to_check:
            try:
                # Run blocking API call in a thread
                event = await asyncio.to_thread(self.api.get_next_event_for_team, team_id)
                if not event or not event.kickoff_utc:
                    continue
                
                now = datetime.now(timezone.utc)
                event_time = event.kickoff_utc.replace(tzinfo=timezone.utc)
                time_diff = event_time - now
                
                # Send reminder if match is strictly in the next 24 hours OR if it's a startup/manual trigger
                if is_startup or (timedelta(0) < time_diff <= timedelta(days=1)):
                    await self._notify_subscribers(team_id, event, subs, is_startup)
            except Exception as e:
                logger.error(f"Error checking team {team_id}: {e}")

    async def _notify_subscribers(self, team_id: str, event, all_subs, is_startup: bool = False):
        team_subs = [s for s in all_subs if s.team_id == team_id]
        
        title = "🚀 Bot Restarted | Jadwal Terdekat" if is_startup else "⚽ Pertandingan Semakin Dekat!"
        desc = f"**{event.name}**"
        
        embed = discord.Embed(
            title=title,
            description=desc,
            color=0x1ABC9C # Professional Turquoise color
        )
        embed.add_field(name="📅 Tanggal", value=event.date, inline=True)
        embed.add_field(name="⏰ Waktu (UTC)", value=event.time, inline=True)
        if event.league:
            embed.add_field(name="🏆 Liga", value=event.league, inline=False)
        if event.venue:
            embed.add_field(name="🏟️ Stadium", value=event.venue, inline=False)
            
        embed.set_footer(text="TheSportsDB API • Jadwal dapat berubah sewaktu-waktu")
        
        for sub in team_subs:
            channel = self.bot.get_channel(sub.channel_id)
            if channel:
                try:
                    # Mengirim notifikasi dengan mention everyone sesuai permintaan, KECUALI saat startup
                    content = "📢 **Status Update Bot**" if is_startup else "@everyone 📢 Reminder Pertandingan!"
                    await channel.send(content=content, embed=embed)
                    logger.info(f"Sent reminder for {event.id} to channel {channel.id}")
                except discord.DiscordException as e:
                    logger.error(f"Failed to send to {sub.channel_id}: {e}")
