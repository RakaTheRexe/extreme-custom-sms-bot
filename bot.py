import os
import logging
import requests
import sqlite3
import asyncio
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
)

# ================= CONFIG =================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
SMS_API_KEY = os.getenv("SMS_API_KEY")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

CHANNEL_USERNAME = "@ExtremeLevelTech"

SMS_API_URL = "http://sms.greenheritageit.com/smsapi"
SENDER_ID = "MultiSports"
TRANSACTION_TYPE = "TransactionType"
CAMPAIGN_ID = "campaignId"

DB_FILE = "database.db"

# ================= LOG =================
logging.basicConfig(level=logging.INFO)

# ================= DATABASE =================
conn = sqlite3.connect(DB_FILE, check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    balance INTEGER DEFAULT 10
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS sms_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    number TEXT,
    message TEXT,
    time TEXT
)
""")

conn.commit()

def get_user(uid):
    cursor.execute("SELECT balance FROM users WHERE user_id=?", (uid,))
    row = cursor.fetchone()
    if row is None:
        cursor.execute("INSERT INTO users (user_id, balance) VALUES (?,?)", (uid, 10))
        conn.commit()
        return 10
    return row[0]

def update_balance(uid, amount):
    cursor.execute("UPDATE users SET balance=? WHERE user_id=?", (amount, uid))
    conn.commit()

def log_sms(uid, number, message):
    cursor.execute(
        "INSERT INTO sms_logs (user_id, number, message, time) VALUES (?,?,?,?)",
        (uid, number, message, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )
    conn.commit()

# ================= FORCE JOIN =================
async def force_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    try:
        member = await context.bot.get_chat_member(CHANNEL_USERNAME, uid)
        if member.status in ["member", "administrator", "creator"]:
            return True
    except:
        pass

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Join Channel", url="https://t.me/ExtremeLevelTech")],
        [InlineKeyboardButton("✅ Verify", callback_data="verify")]
    ])

    await update.message.reply_text(
        "❌ আগে আমাদের চ্যানেলে Join করো",
        reply_markup=kb
    )
    return False

async def verify(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    try:
        member = await context.bot.get_chat_member(CHANNEL_USERNAME, uid)
        if member.status in ["member", "administrator", "creator"]:
            await q.edit_message_text("✅ Verify successful! এখন /start লিখো")
            return
    except:
        pass
    await q.edit_message_text("❌ এখনো Join করোনি")

# ================= COMMANDS =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await force_join(update, context):
        return
    get_user(update.effective_user.id)
    await update.message.reply_text(
        "🤖 Extreme Custom SMS Bot\n\n"
        "📩 /sms number message\n"
        "💰 /balance"
    )

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bal = get_user(update.effective_user.id)
    await update.message.reply_text(f"💰 আপনার ব্যালেন্স: {bal}")

async def sms(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await force_join(update, context):
        return

    uid = update.effective_user.id
    bal = get_user(uid)

    if bal <= 0:
        await update.message.reply_text("❌ ব্যালেন্স শেষ")
        return

    args = context.args
    if len(args) < 2:
        await update.message.reply_text("Usage: /sms 01XXXXXXXX message")
        return

    number = args[0]
    message = " ".join(args[1:])

    params = {
        "apiKey": SMS_API_KEY,
        "senderId": SENDER_ID,
        "transactionType": TRANSACTION_TYPE,
        "campaignId": CAMPAIGN_ID,
        "mobileNo": number,
        "message": message
    }

    r = requests.get(SMS_API_URL, params=params, timeout=15)

    if r.status_code == 200:
        update_balance(uid, bal - 1)
        log_sms(uid, number, message)
        await update.message.reply_text("✅ SMS পাঠানো হয়েছে")
    else:
        await update.message.reply_text("❌ SMS ব্যর্থ")

# ================= ADMIN PANEL =================
async def users_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    cursor.execute("SELECT user_id, balance FROM users")
    rows = cursor.fetchall()

    text = "👑 USER BALANCE LIST\n\n"
    for uid, bal in rows:
        text += f"👤 {uid} → 💰 {bal}\n"

    await update.message.reply_text(text)

async def addbalance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        uid = int(context.args[0])
        amt = int(context.args[1])
        bal = get_user(uid)
        update_balance(uid, bal + amt)
        await update.message.reply_text("✅ Balance added")
    except:
        await update.message.reply_text("Usage: /addbalance user_id amount")

# ================= MAIN =================
async def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("balance", balance))
    app.add_handler(CommandHandler("sms", sms))
    app.add_handler(CommandHandler("users", users_list))   # ADMIN ONLY
    app.add_handler(CommandHandler("addbalance", addbalance))
    app.add_handler(CallbackQueryHandler(verify, pattern="verify"))

    print("Bot running...")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
