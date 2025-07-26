import os
import re
import asyncio
from dotenv import load_dotenv
from pyrogram import Client, filters
from pyrogram.types import Message
from pymongo import MongoClient

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
MONGO_URI = os.getenv("MONGO_URI")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
CHANNELS = os.getenv("CHANNELS").split(",")  # comma-separated list

# Initialize MongoDB
mongo_client = MongoClient(MONGO_URI)
db = mongo_client["mybotdb"]
users_col = db["users"]
posts_col = db["posts"]

# Initialize Pyrogram client
app = Client("my_bot", bot_token=BOT_TOKEN, api_id=API_ID, api_hash=API_HASH)

# Helper function to load users from MongoDB
def get_all_user_ids():
    return [user["user_id"] for user in users_col.find()]

# /start command: register user & show past posts
@app.on_message(filters.command("start") & filters.private)
async def start_handler(client, message: Message):
    user_id = message.from_user.id
    if not users_col.find_one({"user_id": user_id}):
        users_col.insert_one({"user_id": user_id})
    
    await message.reply_text(f"👋 Hello, {message.from_user.first_name}!\nWelcome to this bot.")

    # Send previous posts
    saved_posts = list(posts_col.find())
    for post in saved_posts:
        try:
            if post["type"] == "text":
                await client.send_message(user_id, post["text"])
            elif post["type"] == "photo":
                await client.send_photo(user_id, post["file_id"], caption=post["caption"])
            elif post["type"] == "video":
                await client.send_video(user_id, post["file_id"], caption=post["caption"])
        except Exception as e:
            print(f"❌ Failed to send post to {user_id}: {e}")

# Admin post (broadcast) without buttons
@app.on_message(filters.private & filters.user(ADMIN_ID))
async def admin_post(client, message: Message):
    caption = message.caption or ""
    text = message.text or caption
    clean_text = text

    post_data = {"messages": {}, "type": "", "caption": "", "text": "", "file_id": ""}

    if message.text:
        post_data["type"] = "text"
        post_data["text"] = clean_text

    elif message.photo:
        post_data["type"] = "photo"
        post_data["file_id"] = message.photo.file_id
        post_data["caption"] = clean_text

    elif message.video:
        post_data["type"] = "video"
        post_data["file_id"] = message.video.file_id
        post_data["caption"] = clean_text

    else:
        await message.reply("❌ Unsupported message type.")
        return

    user_ids = get_all_user_ids()

    for uid in user_ids:
        try:
            if post_data["type"] == "text":
                sent = await client.send_message(uid, post_data["text"])
            elif post_data["type"] == "photo":
                sent = await client.send_photo(uid, post_data["file_id"], caption=post_data["caption"])
            elif post_data["type"] == "video":
                sent = await client.send_video(uid, post_data["file_id"], caption=post_data["caption"])

            post_data["messages"][str(uid)] = sent.id

        except Exception as e:
            print(f"❌ Error sending to {uid}: {e}")

    # Send to all channels
    for channel_id in CHANNELS:
        try:
            if post_data["type"] == "text":
                await client.send_message(channel_id, post_data["text"])
            elif post_data["type"] == "photo":
                await client.send_photo(channel_id, post_data["file_id"], caption=post_data["caption"])
            elif post_data["type"] == "video":
                await client.send_video(channel_id, post_data["file_id"], caption=post_data["caption"])
        except Exception as e:
            print(f"❌ Error sending to channel {channel_id}: {e}")

    posts_col.insert_one(post_data)
    await message.reply("✅ Broadcast complete and saved.")

# Run the bot
app.run()
