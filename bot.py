import os
import sqlite3
import logging
import requests
import asyncio
import threading
from datetime import datetime
from flask import Flask, send_file

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

# ================= ENV CONFIG =================
BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
CHANNEL = os.getenv("CHANNEL")
SMS_API_KEY = os.getenv("SMS_API_KEY")
SENDER_ID = os.getenv("SENDER_ID")

SMS_API_URL = "http://sms.greenheritageit.com/smsapi"
TRANSACTION_TYPE = "TransactionType"
CAMPAIGN_ID = "campaignId"

# ================= LOG =================
logging.basicConfig(level=logging.INFO)

# ================= DATABASE =================
db = sqlite3.connect("database.db", check_same_thread=False)
cur = db.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    balance INTEGER DEFAULT 0,
    invited_by INTEGER
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS sms_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    number TEXT,
    message TEXT,
    time TEXT
)
""")
db.commit()

# ================= HELPERS =================
def get_balance(uid):
    cur.execute("SELECT balance FROM users WHERE user_id=?", (uid,))
    r = cur.fetchone()
    if not r:
        cur.execute(
            "INSERT INTO users (user_id, balance) VALUES (?, ?)",
            (uid, 0)
        )
        db.commit()
        return 0
    return r[0]

def add_balance(uid, amt):
    bal = get_balance(uid)
    cur.execute(
        "UPDATE users SET balance=? WHERE user_id=?",
        (bal + amt, uid)
    )
    db.commit()

def log_sms(uid, num, msg):
    cur.execute(
        "INSERT INTO sms_logs (user_id, number, message, time) VALUES (?,?,?,?)",
        (uid, num, msg, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )
    db.commit()

# ================= FORCE JOIN =================
async def force_join(update, context):
    try:
        m = await context.bot.get_chat_member(CHANNEL, update.effective_user.id)
        return m.status in ["member", "administrator", "creator"]
    except:
        return False

# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    if not await force_join(update, context):
        await update.message.reply_text(
            f"❌ আগে Channel join করো:\nhttps://t.me/{CHANNEL.replace('@','')}"
        )
        return

    # Invite reward
    if context.args:
        inviter = int(context.args[0])
        if inviter != uid:
            cur.execute("SELECT invited_by FROM users WHERE user_id=?", (uid,))
            r = cur.fetchone()
            if not r:
                cur.execute(
                    "INSERT INTO users (user_id, balance, invited_by) VALUES (?, ?, ?)",
                    (uid, 5, inviter)
                )
                add_balance(inviter, 5)
                db.commit()

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📩 Send SMS", callback_data="send")],
        [InlineKeyboardButton("💰 Balance", callback_data="balance")],
    ])
    await update.message.reply_text("🤖 Extreme Custom SMS Bot", reply_markup=kb)

# ================= BUTTON HANDLER =================
user_state = {}

async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    if q.data == "balance":
        bal = get_balance(q.from_user.id)
        await q.edit_message_text(f"💰 Balance: {bal}")

    elif q.data == "send":
        if get_balance(q.from_user.id) <= 0:
            await q.edit_message_text("❌ Balance নেই")
            return
        user_state[q.from_user.id] = {"step": "number"}
        await q.edit_message_text("📱 Number পাঠাও:")

# ================= MESSAGE FLOW =================
async def message_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in user_state:
        return

    state = user_state[uid]

    if state["step"] == "number":
        state["number"] = update.message.text
        state["step"] = "message"
        await update.message.reply_text("✉️ Message পাঠাও:")

    elif state["step"] == "message":
        number = state["number"]
        message = update.message.text

        if get_balance(uid) <= 0:
            await update.message.reply_text("❌ Balance শেষ")
            user_state.pop(uid)
            return

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
            add_balance(uid, -1)
            log_sms(uid, number, message)
            await update.message.reply_text("✅ SMS Sent")
        else:
            await update.message.reply_text("❌ SMS Failed")

        user_state.pop(uid)

# ================= ADMIN =================
async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("👤 User Balance", callback_data="userbal")],
        [InlineKeyboardButton("📊 Export SMS Logs", callback_data="export")],
    ])
    await update.message.reply_text("👑 Admin Panel", reply_markup=kb)

async def admin_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    if q.from_user.id != ADMIN_ID:
        return

    if q.data == "userbal":
        cur.execute("SELECT user_id, balance FROM users")
        rows = cur.fetchall()
        txt = "👤 USER BALANCES\n\n"
        for u, b in rows:
            txt += f"{u} → {b}\n"
        await q.edit_message_text(txt)

    elif q.data == "export":
        cur.execute("SELECT * FROM sms_logs")
        rows = cur.fetchall()

        with open("sms_logs.csv", "w", encoding="utf-8") as f:
            f.write("id,user_id,number,message,time\n")
            for r in rows:
                f.write(",".join([str(x) for x in r]) + "\n")

        await q.edit_message_text("📊 Export ready\nVisit /logs")

# ================= WEB DASHBOARD =================
app = Flask(__name__)

@app.route("/")
def home():
    cur.execute("SELECT COUNT(*) FROM users")
    users = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM sms_logs")
    sms = cur.fetchone()[0]
    return f"<h2>Dashboard</h2><p>Users: {users}</p><p>SMS Sent: {sms}</p>"

@app.route("/logs")
def logs():
    return send_file("sms_logs.csv", as_attachment=True)

def run_web():
    app.run(host="0.0.0.0", port=8080)

# ================= MAIN =================
async def main():
    threading.Thread(target=run_web, daemon=True).start()

    bot = ApplicationBuilder().token(BOT_TOKEN).build()
    bot.add_handler(CommandHandler("start", start))
    bot.add_handler(CommandHandler("admin", admin))
    bot.add_handler(CallbackQueryHandler(admin_buttons, pattern="^(userbal|export)$"))
    bot.add_handler(CallbackQueryHandler(buttons))
    bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_flow))

    print("🤖 Bot running...")
    await bot.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
