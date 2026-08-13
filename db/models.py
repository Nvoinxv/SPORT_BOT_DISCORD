from dataclasses import dataclass, asdict, field
from datetime import datetime
from typing import Optional, Literal

# Model lama (subscription user) — dipertahankan untuk backward compatibility
@dataclass
class Subscription:
    channel_id: int
    team_id: str
    team_name: str
    guild_id: Optional[int] = None

    def to_dict(self):
        return asdict(self)


# ---------------------------------------------------------------------------
# MODEL BARU untuk arsitektur konten otomatis 4 kategori
# ---------------------------------------------------------------------------

CategoryType = Literal["branded_shoes", "sport_shoes", "sport_random", "health_edu"]
SourceType = Literal["gemini", "gnews+gemini", "gnews_raw", "newsdata+gemini", 
                     "newsdata_raw", "thesportsdb", "thesportsdb+gemini"]


@dataclass
class ContentLog:
    """
    Riwayat konten yang sudah dikirim ke Discord.
    Digunakan untuk menghindari duplikat dan tracking.
    """
    _id: Optional[str] = None  # MongoDB ObjectId (auto-generated)
    category: CategoryType = "sport_random"
    title: str = ""
    body: str = ""
    source: SourceType = "gemini"
    article_url: Optional[str] = None
    image_url: Optional[str] = None
    channel_id: int = 0
    sent_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> dict:
        data = asdict(self)
        # MongoDB akan generate _id sendiri kalau None
        if data.get("_id") is None:
            data.pop("_id", None)
        return data
    
    @classmethod
    def from_dict(cls, data: dict) -> "ContentLog":
        if "_id" in data:
            data["_id"] = str(data["_id"])
        if "sent_at" in data and isinstance(data["sent_at"], str):
            data["sent_at"] = datetime.fromisoformat(data["sent_at"].replace("Z", "+00:00"))
        return cls(**data)


@dataclass
class ChannelConfig:
    """
    Konfigurasi channel yang aktif untuk mode otomatis.
    Support multiple channel & guild di masa depan.
    """
    _id: Optional[str] = None
    channel_id: int = 0
    guild_id: Optional[int] = None
    channel_name: Optional[str] = None
    is_active: bool = True          # Aktif/nonaktif untuk mode otomatis
    categories_enabled: list = field(default_factory=lambda: [
        "branded_shoes", "sport_shoes", "sport_random", "health_edu"
    ])
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> dict:
        data = asdict(self)
        if data.get("_id") is None:
            data.pop("_id", None)
        return data
    
    @classmethod
    def from_dict(cls, data: dict) -> "ChannelConfig":
        if "_id" in data:
            data["_id"] = str(data["_id"])
        return cls(**data)


@dataclass
class DailyStats:
    """
    Statistik harian pengiriman konten.
    Untuk tracking & monitoring.
    """
    _id: Optional[str] = None
    date: str = ""  # Format: YYYY-MM-DD
    branded_shoes_count: int = 0
    sport_shoes_count: int = 0
    sport_random_count: int = 0
    health_edu_count: int = 0
    total_sent: int = 0
    errors_count: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> dict:
        data = asdict(self)
        if data.get("_id") is None:
            data.pop("_id", None)
        return data
    
    @classmethod
    def from_dict(cls, data: dict) -> "DailyStats":
        if "_id" in data:
            data["_id"] = str(data["_id"])
        return cls(**data)