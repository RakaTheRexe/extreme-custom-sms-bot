# -*- coding: utf-8 -*-

import logging
import sqlite3
import requests
import asyncio
import time
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ConversationHandler
)

# ================== CONFIG ==================
TELEGRAM_TOKEN = "8345293297:AAHv6KfWaFsXJ-rlbJwupBqgTHbKt3CWS5U"
ADMIN_ID = 7008757477
CHANNEL_USERNAME = "@ExtremeLevelTech"

SMS_API_BASE = "http://sms.greenheritageit.com/smsapi"
SMS_API_KEY = "$2y$10$8cKMTQTz6E0hdmbghuOjS.NLPWxolWv99uTlHoLC5VCXWq//Wk1D277"
SENDER_ID = "MultiSports"
TRANSACTION_TYPE = "TransactionType"
CAMPAIGN_ID = "campaignId"

DB_FILE = "bot_database.db"
RATE_LIMIT_SECONDS = 30

PHONE, MESSAGE, CONFIRM = range(3)

# ================== LOGGING ==================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ================== DATABASE ==================
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    c.execute("""CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        balance INTEGER DEFAULT 10,
        ref_count INTEGER DEFAULT 0,
        referrer_id INTEGER,
        join_date TEXT,
        is_banned INTEGER DEFAULT 0
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS sms_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        number TEXT,
        message TEXT,
        timestamp TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS milestone_claims (
        user_id INTEGER,
        level INTEGER
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value INTEGER
    )""")

    c.execute("INSERT OR IGNORE INTO settings VALUES ('sms_enabled',1)")
    c.execute("INSERT OR IGNORE INTO settings VALUES ('ref_enabled',1)")
    c.execute("INSERT OR IGNORE INTO settings VALUES ('broadcast_enabled',1)")

    conn.commit()
    conn.close()

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

# ================== HELPERS ==================
async def is_member(uid, context):
    try:
        m = await context.bot.get_chat_member(CHANNEL_USERNAME, uid)
        return m.status in ["member","administrator","creator"]
    except:
        return False

def get_setting(key):
    conn = get_db()
    r = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    conn.close()
    return r["value"] if r else 0

# ================== START ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    args = context.args

    conn = get_db()
    c = conn.cursor()
    user = c.execute("SELECT * FROM users WHERE user_id=?", (uid,)).fetchone()

    if not user:
        ref = None
        if args and args[0].isdigit():
            r = int(args[0])
            if r != uid:
                chk = c.execute("SELECT * FROM users WHERE user_id=?", (r,)).fetchone()
                if chk and get_setting("ref_enabled"):
                    ref = r
                    c.execute("UPDATE users SET balance=balance+5, ref_count=ref_count+1 WHERE user_id=?", (r,))
                    try:
                        await context.bot.send_message(r, "🎉 New referral joined! +5 balance")
                    except:
                        pass

        c.execute("INSERT INTO users (user_id,referrer_id,join_date) VALUES (?,?,?)",
                  (uid, ref, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()

    conn.close()
    await main_menu(update, context)

# ================== MAIN MENU ==================
async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [
        [InlineKeyboardButton("📩 Send SMS", callback_data="start_sms"),
         InlineKeyboardButton("💰 Balance", callback_data="my_balance")],
        [InlineKeyboardButton("👥 Refer & Earn", callback_data="referral_menu"),
         InlineKeyboardButton("🏆 Leaderboard", callback_data="leaderboard")],
        [InlineKeyboardButton("📜 History", callback_data="history"),
         InlineKeyboardButton("🆘 Support", url="https://t.me/ExtremeLevelTech")]
    ]
    if update.effective_user.id == ADMIN_ID:
        kb.append([InlineKeyboardButton("⚙️ Admin Panel", callback_data="admin_panel")])

    text = "🤖 **Extreme SMS Bot**\n\nChoose an option:"
    if update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
    else:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

# ================== BALANCE ==================
async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = get_db()
    u = conn.execute("SELECT balance,ref_count FROM users WHERE user_id=?",
                     (update.callback_query.from_user.id,)).fetchone()
    conn.close()
    await update.callback_query.edit_message_text(
        f"💰 Balance: {u['balance']}\n👥 Referrals: {u['ref_count']}",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
    )

# ================== SMS FLOW ==================
async def start_sms(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_member(update.callback_query.from_user.id, context):
        await update.callback_query.answer("Join channel first", show_alert=True)
        return ConversationHandler.END
    await update.callback_query.edit_message_text("📱 Enter number:")
    return PHONE

async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["number"] = update.message.text
    await update.message.reply_text("✉️ Enter message:")
    return MESSAGE

async def get_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["msg"] = update.message.text
    kb = [
        [InlineKeyboardButton("✅ Send", callback_data="confirm"),
         InlineKeyboardButton("❌ Cancel", callback_data="cancel")]
    ]
    await update.message.reply_text("Confirm send?", reply_markup=InlineKeyboardMarkup(kb))
    return CONFIRM

async def send_sms(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.callback_query.from_user.id
    conn = get_db()
    bal = conn.execute("SELECT balance FROM users WHERE user_id=?", (uid,)).fetchone()["balance"]

    if bal <= 0:
        await update.callback_query.edit_message_text("❌ Balance finished")
        conn.close()
        return ConversationHandler.END

    params = {
        "apiKey": SMS_API_KEY,
        "senderId": SENDER_ID,
        "transactionType": TRANSACTION_TYPE,
        "campaignId": CAMPAIGN_ID,
        "mobileNo": context.user_data["number"],
        "message": context.user_data["msg"]
    }

    r = requests.get(SMS_API_BASE, params=params)
    if r.status_code == 200:
        conn.execute("UPDATE users SET balance=balance-1 WHERE user_id=?", (uid,))
        conn.execute(
            "INSERT INTO sms_history (user_id,number,message,timestamp) VALUES (?,?,?,?)",
            (uid, context.user_data["number"], context.user_data["msg"],
             datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
        conn.commit()
        await update.callback_query.edit_message_text("✅ SMS Sent")
    else:
        await update.callback_query.edit_message_text("❌ SMS Failed")

    conn.close()
    return ConversationHandler.END

# ================== MAIN ==================
def main():
    init_db()
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    sms_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_sms, pattern="start_sms")],
        states={
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)],
            MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_message)],
            CONFIRM: [CallbackQueryHandler(send_sms, pattern="confirm")]
        },
        fallbacks=[]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(sms_conv)
    app.add_handler(CallbackQueryHandler(main_menu, pattern="main_menu"))
    app.add_handler(CallbackQueryHandler(balance, pattern="my_balance"))

    print("Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
