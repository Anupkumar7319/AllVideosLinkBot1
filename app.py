import os
import json
import re
import threading
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask, request
from config import API_ID, API_HASH, BOT_TOKEN, ADMIN_ID, ONLINE_USERS, USER_FILE, POST_FILE

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

# Load Data
users = set(load_json(USER_FILE))
saved_posts = load_json(POST_FILE)

@app.on_message(filters.command("start") & filters.private)
async def start(client, message: Message):
    user_id = message.from_user.id
    user_name = message.from_user.first_name

    users.add(user_id)
    save_json(USER_FILE, list(users))

    welcome = f"Hello! {user_name}, welcome to @AllVideosLink_Bot."

    await message.reply(
        text=welcome,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(f"📊 Online Users: {ONLINE_USERS}", callback_data="stats")]
        ])
    )

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
            
            if post["type"] == "text":
                await client.send_message(user_id, clean_text, reply_markup=kb)
            elif post["type"] == "photo":
                await client.send_photo(user_id, post["file_id"], caption=clean_text, reply_markup=kb)
            elif post["type"] == "video":
                await client.send_video(user_id, post["file_id"], caption=clean_text, reply_markup=kb)
        except Exception as e:
            print(f"❌ Failed to send to {user_id}: {e}")

@app.on_message(filters.private & filters.user(ADMIN_ID))
async def admin_post(client, message: Message):
    
    pass
    # ====== Delete Last Post from All Users ======
@app.on_message(filters.private & filters.user(ADMIN_ID) & filters.command("delete"))
async def delete_last_post(client, message: Message):
    if saved_posts:
        last_post = saved_posts.pop()
        save_json(POST_FILE, saved_posts)
        for uid in users:
            msg_id = last_post.get("messages", {}).get(str(uid))
            if msg_id:
                try:
                    await client.delete_messages(uid, msg_id)
                except Exception as e:
                    print(f"❌ Failed to delete from {uid}: {e}")
        await message.reply("✅ Last post deleted from all users.")
    else:
        await message.reply("⚠️ No posts to delete.")

# ====== Delete All Posts from All Users ======
@app.on_message(filters.private & filters.user(ADMIN_ID) & filters.command("alldelete"))
async def delete_all_posts(client, message: Message):
    for post in saved_posts:
        for uid in users:
            msg_id = post.get("messages", {}).get(str(uid))
            if msg_id:
                try:
                    await client.delete_messages(uid, msg_id)
                except Exception as e:
                    print(f"❌ Failed to delete from {uid}: {e}")
    saved_posts.clear()
    save_json(POST_FILE, saved_posts)
    await message.reply("✅ All posts deleted from all users.")

# ====== Delete Specific Message ID from All Users ======
@app.on_message(filters.private & filters.user(ADMIN_ID) & filters.command("selectanddelete"))
async def delete_by_id(client, message: Message):
    args = message.text.split()
    if len(args) != 2 or not args[1].isdigit():
        await message.reply("⚠️ Usage: /selectanddelete <message_id>")
        return
    msg_id = int(args[1])
    for uid in users:
        try:
            await client.delete_messages(uid, msg_id)
        except Exception as e:
            print(f"❌ Failed to delete from {uid}: {e}")
    await message.reply(f"✅ Post with message ID {msg_id} deleted from all users.")

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

    for uid in users:
        try:
            if new_post["type"] == "text":
                sent = await client.send_message(uid, clean_text, reply_markup=kb)
            elif new_post["type"] == "photo":
                sent = await client.send_photo(uid, new_post["file_id"], caption=clean_text, reply_markup=kb)
            elif new_post["type"] == "video":
                sent = await client.send_video(uid, new_post["file_id"], caption=clean_text, reply_markup=kb)
            new_post["messages"][str(uid)] = sent.id
        except Exception as e:
            print(f"❌ Failed to send to {uid}: {e}")

    saved_posts.append(new_post)
    save_json(POST_FILE, saved_posts)
    await client.send_message(ADMIN_ID, "✅ Broadcast done and saved.")

@app.on_callback_query(filters.regex("stats"))
async def show_stats(client, callback_query):
    await callback_query.answer(f"Estimated Online Users: {ONLINE_USERS}", show_alert=True)

@web_app.route("/", methods=["GET"])
def root():
    return "Bot is running!", 200

if __name__ == "__main__":
    import threading
    try:
        threading.Thread(target=lambda: web_app.run(host="0.0.0.0", port=5000), daemon=True).start()
        app.run()
    except Exception as e:
        print(f"⚠️ Error: {e}")
        print("🔁 Restarting fallback backup_bot.py...")
        os.system("python3 backup_bot.py")
