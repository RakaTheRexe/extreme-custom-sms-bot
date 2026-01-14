import logging
import requests
import nest_asyncio
import asyncio
import json
import time
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    CallbackQueryHandler
)

# ================= CONFIG =================
TELEGRAM_TOKEN = "8345293297:AAHv6KfWaFsXJ-rlbJwupBqgTHbKt3CWS5U"
ADMIN_ID = 7008757477
CHANNEL_USERNAME = "@ExtremeLevelTech"

SMS_API_URL = "http://sms.greenheritageit.com/smsapi"
SMS_API_KEY = "$2y$10$8cKMTQTz6E0hdmbghuOjS.NLPWxolWv99uTlHoLC5VCXWq//Wk1D277"
MASK_NAME = "MultiSports"

# ================= MEMORY DB =================
users = {}

def today():
    return time.strftime("%Y-%m-%d")

def init_user(uid):
    if uid not in users:
        users[uid] = {
            "balance": 10,
            "daily": 0,
            "day": today()
        }

# ================= SYSTEM =================
nest_asyncio.apply()
logging.basicConfig(level=logging.INFO)

# ================= FORCE JOIN =================
async def force_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    try:
        member = await context.bot.get_chat_member(CHANNEL_USERNAME, uid)
        if member.status in ["member", "administrator", "creator"]:
            return True
    except:
        pass

    keyboard = {
        "inline_keyboard": [
            [{"text": "📢 চ্যানেলে জয়েন করুন", "url": "https://t.me/ExtremeLevelTech"}],
            [{"text": "✅ ভেরিফাই করুন", "callback_data": "verify"}]
        ]
    }

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="🚫 প্রবেশ নিষিদ্ধ\n\nবট ব্যবহার করতে হলে আগে চ্যানেলে জয়েন করুন 👇",
        reply_markup=keyboard
    )
    return False

async def verify(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id

    try:
        member = await context.bot.get_chat_member(CHANNEL_USERNAME, uid)
        if member.status in ["member", "administrator", "creator"]:
            await q.edit_message_text("✅ ভেরিফিকেশন সফল!\nএখন /start লিখুন")
        else:
            await q.edit_message_text("❌ এখনো জয়েন করা হয়নি")
    except:
        await q.edit_message_text("❌ ভেরিফাই ব্যর্থ")

# ================= COMMANDS =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await force_join(update, context):
        return
    init_user(update.effective_user.id)
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=(
            "🚀 Extreme Custom SMS\n\n"
            "📩 SMS পাঠাতে:\n"
            "/sms 01XXXXXXXX hello\n\n"
            "💰 ব্যালেন্স: /balance"
        )
    )

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await force_join(update, context):
        return
    uid = update.effective_user.id
    init_user(uid)
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"💰 আপনার ব্যালেন্স: {users[uid]['balance']} SMS"
    )

async def sms(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await force_join(update, context):
        return

    uid = update.effective_user.id
    init_user(uid)
    args = context.args

    if len(args) < 2:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="⚠️ ফরম্যাট:\n/sms নম্বর মেসেজ"
        )
        return

    if users[uid]["day"] != today():
        users[uid]["daily"] = 0
        users[uid]["day"] = today()

    if users[uid]["balance"] <= 0:
        await context.bot.send_message(update.effective_chat.id, "❌ ব্যালেন্স শেষ")
        return

    if users[uid]["daily"] >= 5:
        await context.bot.send_message(update.effective_chat.id, "❌ আজকের limit শেষ (৫)")
        return

    number = args[0]
    message = " ".join(args[1:])

    payload = {
        "api_key": SMS_API_KEY,
        "transaction_type": "T",
        "campaign_id": "",
        "sms_data": [
            {
                "recipient": number,
                "sender_id": MASK_NAME,
                "message": message
            }
        ]
    }

    requests.post(
        SMS_API_URL,
        data=json.dumps(payload, separators=(',', ':')),
        headers={"Content-Type": "application/json"}
    )

    users[uid]["balance"] -= 1
    users[uid]["daily"] += 1

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="✅ SMS পাঠানো হয়েছে"
    )

async def addbalance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        uid = int(context.args[0])
        amt = int(context.args[1])
        init_user(uid)
        users[uid]["balance"] += amt
        await context.bot.send_message(update.effective_chat.id, "✅ ব্যালেন্স যোগ করা হয়েছে")
    except:
        await context.bot.send_message(update.effective_chat.id, "Usage: /addbalance user amount")

# ================= MAIN =================
async def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("balance", balance))
    app.add_handler(CommandHandler("sms", sms))
    app.add_handler(CommandHandler("addbalance", addbalance))
    app.add_handler(CallbackQueryHandler(verify, pattern="verify"))
    print("Bot running...")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
