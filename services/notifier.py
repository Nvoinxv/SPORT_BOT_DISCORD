"""
NotifierService — Mode Otomatis (Full Loop, Tanpa Subscription User)

Bot memilih satu sumber olahraga secara acak dari AUTO_SOURCES
(EPL, NBA, ATP), lalu mengambil data pertandingan terbaru dari liga itu,
memilih 1 event secara acak, dan mengirim ringkasan AI ke CHANNEL_ID
yang sudah di-set di file .env.

Tidak ada ketergantungan pada data subscription user di MongoDB.
"""

import asyncio
import random
from datetime import datetime, timezone, timedelta

import discord

from bot.config import CHANNEL_ID
from services.content_service import ContentItem  # FIX: import ContentItem
from services.sports_api import TheSportsDBClient, AUTO_SOURCES
from services.gemini_service import GeminiService
from utils.logger import logger

# FIX: definisikan WITA_TZ (Waktu Indonesia Tengah = UTC+8)
WITA_TZ = timezone(timedelta(hours=8))

SPORT_EMOJIS = {
    "Soccer":     "⚽",
    "Basketball": "🏀",
    "Tennis":     "🎾",
}


class NotifierService:
    def __init__(self, bot: discord.Client):
        self.bot = bot
        self.api = TheSportsDBClient()
        self.ai = GeminiService()
        # FIX: simpan channel_id dari config agar bisa dipakai di send_content
        self.channel_id = CHANNEL_ID

    # ------------------------------------------------------------------
    # Entry point BARU — dipanggil oleh scheduler loop (loop.py)
    # ------------------------------------------------------------------
    async def send_content(self, content: ContentItem) -> None:
        """
        Kirim ContentItem ke channel Discord.
        """
        channel = self.bot.get_channel(self.channel_id)
        if not channel:
            logger.error(
                "Channel Discord ID %s tidak ditemukan. "
                "Pastikan CHANNEL_ID sudah benar di .env dan bot sudah di-invite ke server.",
                self.channel_id,
            )
            return

        embed = discord.Embed(
            title=content.title,
            description=content.body,
            color=self._color_for_category(content.category),
            timestamp=datetime.now(WITA_TZ),  # FIX: datetime.now (bukan datetime.datetime.now)
        )
        if content.image_url:
            embed.set_image(url=content.image_url)
        if content.article_url:
            embed.add_field(name="🔗 Sumber", value=content.article_url, inline=False)

        embed.set_footer(text=f"Kategori: {content.category} | Source: {content.source}")

        await channel.send(embed=embed)
        logger.info("Konten [%s] dari source [%s] berhasil dikirim ke Discord.", content.category, content.source)

    # ------------------------------------------------------------------
    # Entry point LAMA — backward compatibility (bisa dipanggil manual)
    # ------------------------------------------------------------------
    async def check_and_notify(self, is_startup: bool = False):
        label = "STARTUP" if is_startup else "SCHEDULER"
        logger.info(f"[{label}] check_and_notify dipanggil.")

        channel = self.bot.get_channel(self.channel_id)
        if not channel:
            logger.error(
                f"Channel ID {self.channel_id} tidak ditemukan. "
                "Pastikan DISCORD_ID_CHANNEL_SEPUTAR_SEPATU sudah benar di .env "
                "dan bot sudah di-invite ke server dengan izin yang cukup."
            )
            return

        # Pilih sumber secara acak (EPL / NBA / ATP)
        source = random.choice(AUTO_SOURCES)
        league_name = source["name"]
        sport = source["sport"]
        league_id = source["league_id"]
        emoji = SPORT_EMOJIS.get(sport, "🏅")

        logger.info(f"[{label}] Sumber terpilih: {league_name} ({sport})")

        # Kirim pesan "sedang memproses" agar channel terlihat ada aktivitas
        status_msg = await channel.send(
            f"{emoji} **Mengambil berita {league_name} terbaru...** ⏳"
        )

        try:
            # Ambil event terbaru dari liga (blocking I/O → dijalankan di thread)
            events = await asyncio.to_thread(
                self.api.get_latest_events_for_league, league_id
            )

            if not events:
                logger.warning(f"[{label}] Tidak ada event ditemukan untuk {league_name}.")
                await status_msg.edit(
                    content=f"{emoji} **{league_name}** — Belum ada pertandingan terbaru yang bisa ditampilkan saat ini."
                )
                return

            # Pilih 1 event secara acak dari maksimal 15 event terakhir
            pool = events[-15:] if len(events) > 15 else events
            event = random.choice(pool)

            logger.info(
                f"[{label}] Event terpilih: {event.name} "
                f"(home={event.home_score}, away={event.away_score})"
            )

            # Minta AI merangkum menjadi berita
            ai_summary = await self.ai.get_event_news_summary(
                sport=sport,
                league=league_name,
                home_team=event.home_team or "Tim Tuan Rumah",
                away_team=event.away_team or "Tim Tamu",
                home_score=event.home_score,
                away_score=event.away_score,
                date=event.date,
                venue=event.venue,
            )

            # Bangun embed
            has_score = event.home_score is not None and event.away_score is not None
            score_display = (
                f"**{event.home_team}** `{event.home_score} - {event.away_score}` **{event.away_team}**"
                if has_score
                else f"{event.home_team} vs {event.away_team}"
            )

            embed = discord.Embed(
                title=f"{emoji} Berita {sport} — {league_name}",
                description=score_display,
                color=self._league_color(sport),
            )
            embed.add_field(name="📰 Ringkasan AI", value=ai_summary, inline=False)
            if event.date:
                embed.add_field(name="📅 Tanggal", value=event.date, inline=True)
            if event.venue:
                embed.add_field(name="🏟️ Venue", value=event.venue, inline=True)

            if event.thumb_url:
                embed.set_image(url=event.thumb_url)

            footer_tag = "🚀 Siaran Langsung Deploy" if is_startup else "🕙 Ringkasan Harian"
            embed.set_footer(text=footer_tag)

            # Edit pesan status → ganti dengan embed final
            await status_msg.edit(content=None, embed=embed)
            logger.info(f"[{label}] Berhasil mengirim berita '{event.name}' ke channel {channel.id}.")

        except Exception as e:
            logger.error(f"[{label}] Gagal memproses berita: {e}", exc_info=True)
            await status_msg.edit(
                content=f"⚠️ Terjadi error saat mengambil berita olahraga: `{e}`"
            )

    # ------------------------------------------------------------------
    # Helper — warna embed per kategori (untuk send_content baru)
    # ------------------------------------------------------------------
    @staticmethod
    def _color_for_category(category: str) -> int:
        colors = {
            "branded_shoes": 0xFF6B00,   # Orange
            "sport_shoes": 0x00BFFF,      # Deep Sky Blue
            "sport_random": 0x32CD32,     # Lime Green
            "health_edu": 0xFF69B4,       # Hot Pink
        }
        return colors.get(category, 0x7289DA)  # Default Discord blurple

    # ------------------------------------------------------------------
    # Helper — warna embed per sport (untuk check_and_notify lama)
    # ------------------------------------------------------------------
    @staticmethod
    def _league_color(sport: str) -> int:
        colors = {
            "Soccer":     0x3D9970,   # hijau lapangan
            "Basketball": 0xE67E22,   # oranye bola basket
            "Tennis":     0xF1C40F,   # kuning bola tenis
        }
        return colors.get(sport, 0x1ABC9C)