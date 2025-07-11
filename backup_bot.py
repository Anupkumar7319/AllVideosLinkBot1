from pyrogram import Client
import os
from dotenv import load_dotenv

load_dotenv()  # 👈 Load .env values

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

app = Client("BackupBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

@app.on_message()
async def hello(client, message):
    await message.reply("✅ Backup bot is running. Main bot failed.")

app.run()
