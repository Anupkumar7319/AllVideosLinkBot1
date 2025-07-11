import os
from dotenv import load_dotenv

load_dotenv()

# Telegram Bot Config
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

# Optional: Just for display
ONLINE_USERS = "5,00,00+"

# Data file backups (not used if using MongoDB)
USER_FILE = "users.json"
POST_FILE = "posts.json"

# Channel IDs (list of integers)
# You must define CHANNELS_ID in your environment like: -1001234567890,-1009876543210
channels_env = os.getenv("CHANNELS_ID", "")
CHANNELS_ID = list(map(int, channels_env.split(","))) if channels_env else []
CHANNELS = CHANNELS_ID

# MongoDB Atlas Config
MONGO_URI = os.getenv("MONGO_URI")  # From .env or Render secrets
MONGO_DB_NAME = "mybotdb"           # You can change DB name here
USER_COLLECTION = "users"
POST_COLLECTION = "posts"
