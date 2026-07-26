from motor.motor_asyncio import AsyncIOMotorClient
from bot.config import MONGO_URI, DB_NAME
from utils.logger import logger

class Database:
    def __init__(self):
        self.client = AsyncIOMotorClient(MONGO_URI)
        self.db = self.client[DB_NAME]
        self.subscriptions = self.db["subscriptions"]

    async def connect(self):
        try:
            # Create unique index for channel and team
            await self.subscriptions.create_index(
                [("channel_id", 1), ("team_id", 1)], 
                unique=True
            )
            logger.info("Connected to MongoDB successfully!")
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}")

    def get_subscriptions_collection(self):
        return self.subscriptions

db = Database()
