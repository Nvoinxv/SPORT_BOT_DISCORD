from motor.motor_asyncio import AsyncIOMotorClient
from bot.config import MONGO_URI, DB_NAME
from utils.logger import logger

class Database:
    def __init__(self):
        self.client = AsyncIOMotorClient(MONGO_URI)
        self.db = self.client[DB_NAME]
        
        # Collection lama (subscription user)
        self.subscriptions = self.db["subscriptions"]
        
        # Collection BARU untuk arsitektur konten otomatis
        self.content_logs = self.db["content_logs"]
        self.channel_configs = self.db["channel_configs"]
        self.daily_stats = self.db["daily_stats"]

    async def connect(self):
        try:
            # Index lama
            await self.subscriptions.create_index(
                [("channel_id", 1), ("team_id", 1)], 
                unique=True
            )
            
            # -----------------------------------------------------------------
            # Index BARU
            # -----------------------------------------------------------------
            
            # ContentLog: index untuk cek duplikat & query by date/category
            await self.content_logs.create_index([("sent_at", -1)])
            await self.content_logs.create_index([("category", 1), ("sent_at", -1)])
            await self.content_logs.create_index([("channel_id", 1), ("sent_at", -1)])
            
            # ChannelConfig: unique index untuk channel
            await self.channel_configs.create_index(
                [("channel_id", 1)], 
                unique=True
            )
            
            # DailyStats: unique index untuk tanggal
            await self.daily_stats.create_index(
                [("date", 1)], 
                unique=True
            )
            
            logger.info("Connected to MongoDB successfully! All indexes created.")
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}")

    def get_subscriptions_collection(self):
        return self.subscriptions
    
    # -----------------------------------------------------------------
    # Getter BARU
    # -----------------------------------------------------------------
    def get_content_logs_collection(self):
        return self.content_logs
    
    def get_channel_configs_collection(self):
        return self.channel_configs
    
    def get_daily_stats_collection(self):
        return self.daily_stats

db = Database()