from db.database import db
from db.models import Subscription
from typing import List

class SubscriptionRepository:
    def __init__(self):
        self.collection = db.get_subscriptions_collection()

    async def add_subscription(self, subscription: Subscription) -> bool:
        """Returns True if added, False if already exists."""
        exists = await self.collection.find_one({
            "channel_id": subscription.channel_id,
            "team_id": subscription.team_id
        })
        if exists:
            return False
        
        await self.collection.insert_one(subscription.to_dict())
        return True

    async def remove_subscription(self, channel_id: int, team_id: str) -> bool:
        """Returns True if removed, False if not found."""
        result = await self.collection.delete_one({
            "channel_id": channel_id,
            "team_id": team_id
        })
        return result.deleted_count > 0

    async def get_all_subscriptions(self) -> List[Subscription]:
        cursor = self.collection.find({})
        subs = []
        async for doc in cursor:
            subs.append(Subscription(
                channel_id=doc["channel_id"],
                team_id=doc["team_id"],
                team_name=doc["team_name"],
                guild_id=doc.get("guild_id")
            ))
        return subs

    async def get_subscriptions_by_channel(self, channel_id: int) -> List[Subscription]:
        cursor = self.collection.find({"channel_id": channel_id})
        subs = []
        async for doc in cursor:
            subs.append(Subscription(
                channel_id=doc["channel_id"],
                team_id=doc["team_id"],
                team_name=doc["team_name"],
                guild_id=doc.get("guild_id")
            ))
        return subs
