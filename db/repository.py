"""
Repository layer untuk MongoDB.
Menyediakan abstraction CRUD untuk semua collection.
"""

from __future__ import annotations

import logging
from datetime import datetime, date
from typing import Optional

from db.database import db
from db.models import ContentLog, ChannelConfig, DailyStats, Subscription

logger = logging.getLogger(__name__)


class ContentLogRepository:
    """Repository untuk riwayat konten yang sudah dikirim."""

    def __init__(self):
        self.collection = db.get_content_logs_collection()

    async def create(self, log: ContentLog) -> str:
        """Simpan log konten yang baru dikirim. Return inserted _id."""
        result = await self.collection.insert_one(log.to_dict())
        logger.info("ContentLog created: %s | category=%s", result.inserted_id, log.category)
        return str(result.inserted_id)

    async def get_recent_by_category(
        self,
        category: str,
        hours: int = 24,
        limit: int = 10,
    ) -> list[ContentLog]:
        """Ambil log konten terbaru berdasarkan kategori (untuk cek duplikat)."""
        from_time = datetime.utcnow() - __import__('datetime').timedelta(hours=hours)
        cursor = self.collection.find({
            "category": category,
            "sent_at": {"$gte": from_time}
        }).sort("sent_at", -1).limit(limit)
        
        docs = await cursor.to_list(length=limit)
        return [ContentLog.from_dict(d) for d in docs]

    async def get_today_count(self, category: str | None = None) -> int:
        """Hitung berapa konten yang sudah dikirim hari ini."""
        today_start = datetime.combine(date.today(), __import__('datetime').time.min)
        query = {"sent_at": {"$gte": today_start}}
        if category:
            query["category"] = category
        return await self.collection.count_documents(query)

    async def exists_similar_today(self, title: str, category: str) -> bool:
        """
        Cek apakah konten dengan judul serupa sudah dikirim hari ini.
        Digunakan untuk menghindari duplikat judul.
        """
        today_start = datetime.combine(date.today(), __import__('datetime').time.min)
        count = await self.collection.count_documents({
            "category": category,
            "title": {"$regex": title[:30], "$options": "i"},  # Partial match
            "sent_at": {"$gte": today_start}
        })
        return count > 0


class ChannelConfigRepository:
    """Repository untuk konfigurasi channel Discord."""

    def __init__(self):
        self.collection = db.get_channel_configs_collection()

    async def get_active_channels(self) -> list[ChannelConfig]:
        """Ambil semua channel yang aktif untuk mode otomatis."""
        cursor = self.collection.find({"is_active": True})
        docs = await cursor.to_list(length=100)
        return [ChannelConfig.from_dict(d) for d in docs]

    async def get_by_channel_id(self, channel_id: int) -> Optional[ChannelConfig]:
        """Ambil konfigurasi channel tertentu."""
        doc = await self.collection.find_one({"channel_id": channel_id})
        return ChannelConfig.from_dict(doc) if doc else None

    async def upsert(self, config: ChannelConfig) -> str:
        """Insert atau update konfigurasi channel."""
        config.updated_at = datetime.utcnow()
        result = await self.collection.replace_one(
            {"channel_id": config.channel_id},
            config.to_dict(),
            upsert=True
        )
        if result.upserted_id:
            return str(result.upserted_id)
        # Kalau update, cari dokumennya
        doc = await self.collection.find_one({"channel_id": config.channel_id})
        return str(doc["_id"]) if doc else ""

    async def disable_channel(self, channel_id: int) -> bool:
        """Nonaktifkan channel."""
        result = await self.collection.update_one(
            {"channel_id": channel_id},
            {"$set": {"is_active": False, "updated_at": datetime.utcnow()}}
        )
        return result.modified_count > 0


class DailyStatsRepository:
    """Repository untuk statistik harian pengiriman konten."""

    def __init__(self):
        self.collection = db.get_daily_stats_collection()

    async def increment(self, category: str, errors: int = 0) -> None:
        """
        Increment counter untuk kategori tertentu hari ini.
        Dipanggil setiap kali berhasil mengirim konten.
        """
        today = date.today().isoformat()
        field_map = {
            "branded_shoes": "branded_shoes_count",
            "sport_shoes": "sport_shoes_count",
            "sport_random": "sport_random_count",
            "health_edu": "health_edu_count",
        }
        field = field_map.get(category, "sport_random_count")
        
        update = {
            "$inc": {
                field: 1,
                "total_sent": 1,
                "errors_count": errors,
            },
            "$setOnInsert": {
                "date": today,
                "created_at": datetime.utcnow(),
            },
            "$set": {
                "updated_at": datetime.utcnow(),
            }
        }
        
        await self.collection.update_one(
            {"date": today},
            update,
            upsert=True
        )
        logger.debug("DailyStats incremented: %s | category=%s", today, category)

    async def get_today(self) -> Optional[DailyStats]:
        """Ambil statistik hari ini."""
        today = date.today().isoformat()
        doc = await self.collection.find_one({"date": today})
        return DailyStats.from_dict(doc) if doc else None

    async def get_range(self, start_date: str, end_date: str) -> list[DailyStats]:
        """Ambil statistik dalam range tanggal (YYYY-MM-DD)."""
        cursor = self.collection.find({
            "date": {"$gte": start_date, "$lte": end_date}
        }).sort("date", 1)
        docs = await cursor.to_list(length=100)
        return [DailyStats.from_dict(d) for d in docs]


class SubscriptionRepository:
    """Repository lama untuk subscription user (backward compatibility)."""

    def __init__(self):
        self.collection = db.get_subscriptions_collection()

    async def create(self, sub: Subscription) -> str:
        result = await self.collection.insert_one(sub.to_dict())
        return str(result.inserted_id)

    async def get_by_channel(self, channel_id: int) -> list[Subscription]:
        cursor = self.collection.find({"channel_id": channel_id})
        docs = await cursor.to_list(length=100)
        return [Subscription(**d) for d in docs]

    async def delete(self, channel_id: int, team_id: str) -> bool:
        result = await self.collection.delete_one({
            "channel_id": channel_id,
            "team_id": team_id
        })
        return result.deleted_count > 0