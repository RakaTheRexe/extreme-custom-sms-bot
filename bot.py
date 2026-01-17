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
)

# ================= BASIC CONFIG =================
BOT_TOKEN = "8345293297:AAHv6KfWaFsXJ-rlbJwupBqgTHbKt3CWS5U"
ADMIN_ID = 7008757477
CHANNEL = "@ExtremeLevelTech"

SMS_API_URL = "http://sms.greenheritageit.com/smsapi"
SMS_API_KEY = "$2y$10$8cKMTQTz6E0hdmbghuOjS.NLPWxolWv99uTlHoLC5VCXWq//Wk1D277"
SENDER_ID = "MultiSports"
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
    balance INTEGER DEFAULT 10
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
        cur.execute("INSERT INTO users (user_id, balance) VALUES (?,?)", (uid, 10))
        db.commit()
        return 10
    return r[0]

def add_balance(uid, amt):
    bal = get_balance(uid)
    cur.execute("UPDATE users SET balance=? WHERE user_id=?", (bal + amt, uid))
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

# ================= USER COMMANDS =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await force_join(update, context):
        await update.message.reply_text(
            f"❌ আগে Channel join করো:\nhttps://t.me/{CHANNEL.replace('@','')}"
        )
        return
    await update.message.reply_text(
        "🤖 Extreme Custom SMS Bot\n\n"
        "/send number message\n"
        "/balance"
    )

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bal = get_balance(update.effective_user.id)
    await update.message.reply_text(f"💰 Balance: {bal}")

async def send_sms(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await force_join(update, context):
        return

    uid = update.effective_user.id
    bal = get_balance(uid)

    if bal <= 0:
        await update.message.reply_text("❌ Balance শেষ")
        return

    if len(context.args) < 2:
        await update.message.reply_text("Usage: /send number message")
        return

    number = context.args[0]
    message = " ".join(context.args[1:])

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

# ================= INLINE ADMIN PANEL =================
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

        await q.edit_message_text("📊 SMS log export ready\nDownload from Web Dashboard")

# ================= MINI WEB DASHBOARD =================
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
    threading.Thread(target=run_web).start()

    bot = ApplicationBuilder().token(BOT_TOKEN).build()
    bot.add_handler(CommandHandler("start", start))
    bot.add_handler(CommandHandler("balance", balance))
    bot.add_handler(CommandHandler("send", send_sms))
    bot.add_handler(CommandHandler("admin", admin))
    bot.add_handler(CallbackQueryHandler(admin_buttons))

    print("🤖 Bot running...")
    await bot.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
