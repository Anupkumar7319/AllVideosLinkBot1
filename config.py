import os
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
ONLINE_USERS = "5,00,00+"

USER_FILE = "users.json"
POST_FILE = "posts.json"

CHANNELS = CHANNELS_ID
CHANNELS_ID = ["CHANNELS_ID"]

MONGO_URI = os.getenv("MONGO_URI")  # MongoDB connection URI from Render

MONGO_DB_NAME = "mybotdb"
USER_COLLECTION = "users"
POST_COLLECTION = "posts"
