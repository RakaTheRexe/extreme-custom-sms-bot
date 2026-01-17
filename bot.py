# -*- coding: utf-8 -*-

import logging
import sqlite3
import requests
import asyncio
import nest_asyncio
import time
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CallbackQueryHandler,
    MessageHandler,
    filters
)

# ================= CONFIG =================
BOT_TOKEN = "8345293297:AAHv6KfWaFsXJ-rlbJwupBqgTHbKt3CWS5U"
ADMIN_ID = 7008757477
CHANNEL_USERNAME = "@ExtremeLevelTech"

SMS_API_BASE = "http://sms.greenheritageit.com/smsapi"
SMS_API_KEY = "$2y$10$8cKMTQTz6E0hdmbghuOjS.NLPWxolWv99uTlHoLC5VCXWq//Wk1D277"
SENDER_ID = "MultiSports"
TRANSACTION_TYPE = "TransactionType"
CAMPAIGN_ID = "campaignId"

SUPPORT_USERNAME = "RexeTheRaka"
DEFAULT_BALANCE = 10

# ================= LOG =================
logging.basicConfig(level=logging.INFO)
nest_asyncio.apply()

# ================= DATABASE =================
db = sqlite3.connect("bot.db", check_same_thread=False)
c = db.cursor()

c.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    balance INTEGER DEFAULT 10
)
""")
db.commit()

def get_user(uid):
    c.execute("SELECT * FROM users WHERE user_id=?", (uid,))
    return c.fetchone()

def add_user(uid):
    if not get_user(uid):
        c.execute(
            "INSERT INTO users (user_id, balance) VALUES (?,?)",
            (uid, DEFAULT_BALANCE)
        )
        db.commit()

def update_balance(uid, amt):
    c.execute(
        "UPDATE users SET balance = balance + ? WHERE user_id=?",
        (amt, uid)
    )
    db.commit()

# ================= FORCE JOIN =================
async def force_join(update, context):
    try:
        member = await context.bot.get_chat_member(
            CHANNEL_USERNAME,
            update.effective_user.id
        )
        if member.status in ["member", "administrator", "creator"]:
            return True
    except:
        pass

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Join Channel", url="https://t.me/ExtremeLevelTech")],
        [InlineKeyboardButton("✅ Verify", callback_data="verify")]
    ])

    await update.effective_chat.send_message(
        "❌ বট ব্যবহার করতে হলে আগে চ্যানেলে Join করতে হবে",
        reply_markup=keyboard
    )
    return False

# ================= MENU =================
def user_menu():
    return ReplyKeyboardMarkup(
        [
            ["📩 Send SMS", "💰 Balance"],
            ["🆘 Support"]
        ],
        resize_keyboard=True
    )

# ================= VERIFY =================
async def verify(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    add_user(q.from_user.id)
    await q.message.reply_text(
        "✅ Verify Successful!",
        reply_markup=user_menu()
    )

# ================= HANDLER =================
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await force_join(update, context):
        return

    uid = update.effective_user.id
    text = update.message.text
    add_user(uid)

    if text == "💰 Balance":
        user = get_user(uid)
        await update.message.reply_text(
            f"💰 Your Balance: {user[1]} SMS"
        )

    elif text == "📩 Send SMS":
        await update.message.reply_text(
            "SMS system active ✔️"
        )

    elif text == "🆘 Support":
        await update.message.reply_text(
            f"🆘 Support Contact:\nhttps://t.me/{SUPPORT_USERNAME}"
        )

# ================= MAIN =================
async def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    app.add_handler(CallbackQueryHandler(verify, pattern="^verify$"))

    print("Bot running...")
    await app.run_polling()

# 🔥 VERY IMPORTANT (KOYEB SAFE)
loop = asyncio.get_event_loop()
loop.run_until_complete(main())
