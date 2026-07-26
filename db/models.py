from dataclasses import dataclass, asdict
from typing import Optional

@dataclass
class Subscription:
    channel_id: int
    team_id: str
    team_name: str
    guild_id: Optional[int] = None

    def to_dict(self):
        return asdict(self)
