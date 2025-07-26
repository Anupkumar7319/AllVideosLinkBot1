import asyncio
from pyrogram.errors import FloodWait
from pymongo import MongoClient
from config import MONGO_URI, MONGO_DB_NAME, USER_COLLECTION, POST_COLLECTION

mongo_client = MongoClient(MONGO_URI)
db = mongo_client[MONGO_DB_NAME]
users_collection = db[USER_COLLECTION]
posts_collection = db[POST_COLLECTION]

import os
import json
import threading
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask, request
from config import API_ID, API_HASH, BOT_TOKEN, ADMIN_ID, ONLINE_USERS, USER_FILE, POST_FILE, CHANNELS_ID

app = Client("AllVideosLink_Bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
web_app = Flask(__name__)

# JSON helper functions (not used now if using MongoDB only)
def load_json(file_path):
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            return json.load(f)
    return []

def save_json(file_path, data):
    with open(file_path, "w") as f:
        json.dump(data, f, indent=2)

# Start command
@app.on_message(filters.command("start") & filters.private)
async def start(client, message: Message):
    user_id = message.from_user.id
    user_name = message.from_user.first_name

    users_collection.update_one(
        {"user_id": user_id},
        {"$set": {"name": user_name}},
        upsert=True
    )

    welcome = f"Hello! {user_name}, welcome to @AllVideosLink_Bot."

    await message.reply(
        text=welcome,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(f"📊 Online Users: {ONLINE_USERS}", callback_data="stats")]
        ])
    )

    saved_posts = list(posts_collection.find())
    for post in saved_posts:
        try:
            clean_text = post.get("text") or post.get("caption", "")
            if post["type"] == "text":
                await client.send_message(user_id, clean_text)
            elif post["type"] == "photo":
                await client.send_photo(user_id, post["file_id"], caption=clean_text)
            elif post["type"] == "video":
                await client.send_video(user_id, post["file_id"], caption=clean_text)
        except Exception as e:
            print(f"❌ Failed to send to {user_id}: {e}")

# Admin broadcast
@app.on_message(filters.private & filters.user(ADMIN_ID))
async def admin_post(client, message: Message):
    clean_text = message.text or message.caption or ""
    kb = None  # No buttons now

    if message.text:
        new_post = {"type": "text", "text": clean_text}
    elif message.photo:
        new_post = {"type": "photo", "file_id": message.photo.file_id, "caption": clean_text}
    elif message.video:
        new_post = {"type": "video", "file_id": message.video.file_id, "caption": clean_text}
    else:
        return

    new_post["messages"] = {}

    for user in users_collection.find():
        uid = user["user_id"]
        try:
            if new_post["type"] == "text":
                sent = await client.send_message(uid, clean_text)
            elif new_post["type"] == "photo":
                sent = await client.send_photo(uid, new_post["file_id"], caption=clean_text)
            elif new_post["type"] == "video":
                sent = await client.send_video(uid, new_post["file_id"], caption=clean_text)

            new_post["messages"][str(uid)] = sent.id
            await asyncio.sleep(1)
        except FloodWait as e:
            print(f"🚫 FloodWait for {uid}: {e.value} seconds")
            await asyncio.sleep(e.value)
        except Exception as e:
            print(f"❌ Error sending to {uid}: {e}")

    posts_collection.insert_one(new_post)

    # Forward to channels/groups
    for channel_id in CHANNELS_ID:
        try:
            if message.text:
                await client.send_message(channel_id, message.text)
            elif message.photo:
                await client.send_photo(channel_id, message.photo.file_id, caption=clean_text)
            elif message.video:
                await client.send_video(channel_id, message.video.file_id, caption=clean_text)
        except Exception as e:
            print(f"❌ Channel forward failed to {channel_id}: {e}")

    await client.send_message(ADMIN_ID, "✅ Broadcast done and saved.")

# Delete last post
@app.on_message(filters.private & filters.user(ADMIN_ID) & filters.command("delete"))
async def delete_last_post(client, message: Message):
    saved_posts = list(posts_collection.find())
    if saved_posts:
        last_post = saved_posts.pop()
        posts_collection.delete_one({"_id": last_post["_id"]})
        for user in users_collection.find():
            uid = user["user_id"]
            msg_id = last_post.get("messages", {}).get(str(uid))
            if msg_id:
                try:
                    await client.delete_messages(uid, msg_id)
                except Exception as e:
                    print(f"❌ Failed to delete from {uid}: {e}")
        await message.reply("✅ Last post deleted from all users.")
    else:
        await message.reply("⚠️ No posts to delete.")

# Delete all posts
@app.on_message(filters.private & filters.user(ADMIN_ID) & filters.command("alldelete"))
async def delete_all_posts(client, message: Message):
    saved_posts = list(posts_collection.find())
    for post in saved_posts:
        for user in users_collection.find():
            uid = user["user_id"]
            msg_id = post.get("messages", {}).get(str(uid))
            if msg_id:
                try:
                    await client.delete_messages(uid, msg_id)
                except Exception as e:
                    print(f"❌ Failed to delete from {uid}: {e}")
    posts_collection.delete_many({})
    await message.reply("✅ All posts deleted from all users.")

# Delete by message ID
@app.on_message(filters.private & filters.user(ADMIN_ID) & filters.command("selectanddelete"))
async def delete_by_id(client, message: Message):
    args = (message.text or "").split()
    if len(args) != 2 or not args[1].isdigit():
        await message.reply("⚠️ Usage: /selectanddelete <message_id>")
        return

    msg_id = int(args[1])
    for user in users_collection.find():
        uid = user["user_id"]
        try:
            await client.delete_messages(uid, msg_id)
        except Exception as e:
            print(f"❌ Failed to delete from {uid}: {e}")
    await message.reply(f"✅ Post with message ID {msg_id} deleted from all users.")

# Stats callback
@app.on_callback_query(filters.regex("stats"))
async def show_stats(client, callback_query):
    await callback_query.answer(f"Estimated Online Users: {ONLINE_USERS}", show_alert=True)

# Root health check
@web_app.route("/", methods=["GET"])
def root():
    return "Bot is running!", 200

# Auto-forward admin non-command messages to channels
@app.on_message(filters.private & filters.user(ADMIN_ID) & ~filters.command(["start", "delete", "alldelete", "selectanddelete", "resendall"]))
async def auto_forward_handler(client, message: Message):
    clean_text = message.text or message.caption or ""
    kb = None  # No buttons now

    if message.text:
        post_data = {"type": "text", "text": clean_text}
    elif message.photo:
        post_data = {"type": "photo", "file_id": message.photo.file_id, "caption": clean_text}
    elif message.video:
        post_data = {"type": "video", "file_id": message.video.file_id, "caption": clean_text}
    else:
        print("⚠️ Unsupported message type")
        return

    post_data["messages"] = {}
    posts_collection.insert_one(post_data)

    for channel_id in CHANNELS_ID:
        try:
            if post_data["type"] == "text":
                await client.send_message(channel_id, clean_text)
            elif post_data["type"] == "photo":
                await client.send_photo(channel_id, post_data["file_id"], caption=clean_text)
            elif post_data["type"] == "video":
                await client.send_video(channel_id, post_data["file_id"], caption=clean_text)
            print(f"✅ Auto-forwarded to {channel_id}")
        except Exception as e:
            print(f"❌ Auto-forward failed to {channel_id}: {e}")

# Re-send all saved posts to channels
@app.on_message(filters.private & filters.user(ADMIN_ID) & filters.command("resendall"))
async def resend_all_posts(client, message: Message):
    saved_posts = list(posts_collection.find())
    if not saved_posts:
        await message.reply("⚠️ No posts found in database.")
        return

    count = 0
    for post in saved_posts:
        try:
            clean_text = post.get("text") or post.get("caption", "")
            post_type = post.get("type")
            file_id = post.get("file_id")

            for channel_id in CHANNELS_ID:
                try:
                    if post_type == "text":
                        await client.send_message(channel_id, clean_text)
                    elif post_type == "photo":
                        await client.send_photo(channel_id, file_id, caption=clean_text)
                    elif post_type == "video":
                        await client.send_video(channel_id, file_id, caption=clean_text)
                    count += 1
                except Exception as e:
                    print(f"❌ Failed to send to {channel_id}: {e}")
        except Exception as e:
            print(f"❌ Error processing post: {e}")

    await message.reply(f"✅ Re-sent {count} post(s) to all channels/groups.")

# Run Flask + Pyrogram
if __name__ == "__main__":
    try:
        threading.Thread(target=lambda: web_app.run(host="0.0.0.0", port=5000), daemon=True).start()
        app.run()
    except Exception as e:
        print(f"⚠️ Error: {e}")
        print("🔁 Restarting fallback backup_bot.py...")
        os.system("python3 backup_bot.py")
