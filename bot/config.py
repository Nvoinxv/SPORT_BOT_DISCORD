import os
from dotenv import load_dotenv

load_dotenv()

# Discord settings
DISCORD_TOKEN = os.getenv("DISCORD_AKUN_API")
if not DISCORD_TOKEN:
    raise ValueError("DISCORD_AKUN_API is missing from environment variables!")

# MongoDB settings
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/sportbot")
DB_NAME = "sportbot"

# Optional specific channels
CHANNEL_ID = os.getenv("DISCORD_ID_CHANNEL_SEPUTAR_SEPATU")
if CHANNEL_ID:
    CHANNEL_ID = int(CHANNEL_ID)

GUILD_ID = os.getenv("DISCORD_GROUP_ID")
if GUILD_ID:
    GUILD_ID = int(GUILD_ID)
