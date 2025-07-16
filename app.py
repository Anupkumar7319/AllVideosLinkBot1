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
import re
import threading
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask, request
from config import API_ID, API_HASH, BOT_TOKEN, ADMIN_ID, ONLINE_USERS, USER_FILE, POST_FILE, CHANNELS_ID

# Initialize Clients
app = Client("AllVideosLink_Bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
web_app = Flask(__name__)

# Helper Functions
def load_json(file_path):
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            return json.load(f)
    return []

def save_json(file_path, data):
    with open(file_path, "w") as f:
        json.dump(data, f, indent=2)

def build_keyboard(buttons):
    return InlineKeyboardMarkup([[InlineKeyboardButton(btn["text"], url=btn["url"])] for btn in buttons])

def extract_links(text):
    return re.findall(r'https?://\S+', text) if text else []

def remove_links_from_text(text, links):
    for link in links:
        text = text.replace(link, '')
    return text.strip()

# ✅ 0. Start Command Handler
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
            buttons = post.get("buttons", [])
            kb = build_keyboard(buttons) if buttons else None
            clean_text = post.get("text") or post.get("caption", "")

            if post["type"] == "text":
                await client.send_message(user_id, clean_text, reply_markup=kb)
            elif post["type"] == "photo":
                await client.send_photo(user_id, post["file_id"], caption=clean_text, reply_markup=kb)
            elif post["type"] == "video":
                await client.send_video(user_id, post["file_id"], caption=clean_text, reply_markup=kb)
        except Exception as e:
            print(f"❌ Failed to send to {user_id}: {e}")

# ✅ 1. Admin Broadcast Function
@app.on_message(filters.private & filters.user(ADMIN_ID))
async def admin_post(client, message: Message):
    caption = message.caption or ""
    text = message.text or caption
    links = extract_links(text)
    clean_text = remove_links_from_text(text, links)
    buttons = [{"text": f"🔗 Visit Link {i+1}", "url": link} for i, link in enumerate(links)]
    kb = build_keyboard(buttons) if buttons else None

    if message.text:
        new_post = {"type": "text", "text": clean_text, "buttons": buttons}
    elif message.photo:
        new_post = {"type": "photo", "file_id": message.photo.file_id, "caption": clean_text, "buttons": buttons}
    elif message.video:
        new_post = {"type": "video", "file_id": message.video.file_id, "caption": clean_text, "buttons": buttons}
    else:
        return

    new_post["messages"] = {}
    
    for user in users_collection.find():
        uid = user["user_id"]
        try:
            if new_post["type"] == "text":
                sent = await client.send_message(uid, clean_text, reply_markup=kb)
            elif new_post["type"] == "photo":
                sent = await client.send_photo(uid, new_post["file_id"], caption=clean_text, reply_markup=kb)
            elif new_post["type"] == "video":
                sent = await client.send_video(uid, new_post["file_id"], caption=clean_text, reply_markup=kb)

            new_post["messages"][str(uid)] = sent.id

            await asyncio.sleep(1)  # 🔁 Delay between each message

        except FloodWait as e:
            print(f"🚫 FloodWait: Sleeping for {e.value} seconds for user {uid}")
            await asyncio.sleep(e.value)
        except Exception as e:
            print(f"❌ Failed to send to {uid}: {e}")
            
    posts_collection.insert_one(new_post)
    saved_posts = list(posts_collection.find())

    # 🔁 Broadcast to all registered channels
    for channel_id in CHANNELS_ID:
        try:
            if message.text:
                await client.send_message(channel_id, message.text, reply_markup=kb)
            elif message.photo:
                await client.send_photo(channel_id, message.photo.file_id, caption=clean_text, reply_markup=kb)
            elif message.video:
                await client.send_video(channel_id, message.video.file_id, caption=clean_text, reply_markup=kb)
        except Exception as e:
            print(f"❌ Failed to send to channel {channel_id}: {e}")

    await client.send_message(ADMIN_ID, "✅ Broadcast done and saved.")

# ✅ 2. Delete Last Post
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

# ✅ 3. Delete All Posts
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

# ✅ 4. Delete by Message ID
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

# ✅ 5. Callback Query Handler for Stats
@app.on_callback_query(filters.regex("stats"))
async def show_stats(client, callback_query):
    await callback_query.answer(f"Estimated Online Users: {ONLINE_USERS}", show_alert=True)

# ✅ 6. Flask Webhook Root Check
@web_app.route("/", methods=["GET"])
def root():
    return "Bot is running!", 200

# ✅ 7. Auto-forward any user message to all channels
@app.on_message(filters.private & filters.user(ADMIN_ID) & ~filters.command(["start", "delete", "alldelete", "selectanddelete", "resendall"]))
async def auto_forward_handler(client, message: Message):
    print("⚙️ Auto-forward handler triggered")

    caption = message.caption or ""
    text = message.text or caption
    links = extract_links(text)
    clean_text = remove_links_from_text(text, links)
    buttons = [{"text": f"🔗 Visit Link {i+1}", "url": link} for i, link in enumerate(links)]
    kb = build_keyboard(buttons) if buttons else None

    if message.text:
        post_data = {"type": "text", "text": clean_text, "buttons": buttons}
    elif message.photo:
        post_data = {"type": "photo", "file_id": message.photo.file_id, "caption": clean_text, "buttons": buttons}
    elif message.video:
        post_data = {"type": "video", "file_id": message.video.file_id, "caption": clean_text, "buttons": buttons}
    else:
        print("⚠️ Unsupported message type")
        return

    post_data["messages"] = {}
    posts_collection.insert_one(post_data)
    print(f"📦 Saved post to MongoDB: {post_data['type']}")

    for channel_id in CHANNELS_ID:
        try:
            if post_data["type"] == "text":
                await client.send_message(channel_id, clean_text, reply_markup=kb)
            elif post_data["type"] == "photo":
                await client.send_photo(channel_id, post_data["file_id"], caption=clean_text, reply_markup=kb)
            elif post_data["type"] == "video":
                await client.send_video(channel_id, post_data["file_id"], caption=clean_text, reply_markup=kb)

            print(f"✅ Auto-forwarded to {channel_id}")

        except Exception as e:
            print(f"❌ Auto-forward failed to {channel_id}: {e}")

# ✅ 8. Admin Command to Re-send All MongoDB Posts to Channel(s)
@app.on_message(filters.private & filters.user(ADMIN_ID) & filters.command("resendall"))
async def resend_all_posts(client, message: Message):
    saved_posts = list(posts_collection.find())

    if not saved_posts:
        await message.reply("⚠️ No posts found in database.")
        return

    count = 0

    for post in saved_posts:
        try:
            buttons = post.get("buttons", [])
            kb = build_keyboard(buttons) if buttons else None
            clean_text = post.get("text") or post.get("caption", "")
            post_type = post.get("type")
            file_id = post.get("file_id")

            for channel_id in CHANNELS_ID:
                try:
                    if post_type == "text":
                        await client.send_message(channel_id, clean_text, reply_markup=kb)
                    elif post_type == "photo" and file_id:
                        await client.send_photo(channel_id, file_id, caption=clean_text, reply_markup=kb)
                    elif post_type == "video" and file_id:
                        await client.send_video(channel_id, file_id, caption=clean_text, reply_markup=kb)
                    else:
                        print(f"⚠️ Skipping post due to missing file_id or unknown type: {post}")
                        continue
                    count += 1
                except Exception as e:
                    print(f"❌ Failed to send to {channel_id}: {e}")

        except Exception as e:
            print(f"❌ Error processing post: {e}")

    await message.reply(f"✅ Re-sent {count} post(s) to all channels/groups.")
    
            

# ✅ 9. Run Flask + Pyrogram Client
if __name__ == "__main__":
    try:
        threading.Thread(target=lambda: web_app.run(host="0.0.0.0", port=5000), daemon=True).start()
        app.run()
    except Exception as e:
        print(f"⚠️ Error: {e}")
        print("🔁 Restarting fallback backup_bot.py...")
        os.system("python3 backup_bot.py")
