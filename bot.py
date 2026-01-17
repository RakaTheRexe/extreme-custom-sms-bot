import os
import sqlite3
import requests
from datetime import datetime, timedelta

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ================= ENV =================
BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
CHANNEL = os.getenv("CHANNEL")

SMS_API_URL = os.getenv("SMS_API_URL")
SMS_API_KEY = os.getenv("SMS_API_KEY")
SENDER_ID = os.getenv("SENDER_ID")

# ================= DATABASE =================
db = sqlite3.connect("database.db", check_same_thread=False)
cur = db.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    balance INTEGER DEFAULT 5,
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
        cur.execute("INSERT INTO users (user_id, balance) VALUES (?,5)", (uid,))
        db.commit()
        return 5
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
            f"❌ আগে channel join করুন:\nhttps://t.me/{CHANNEL.replace('@','')}"
        )
        return

    # Invite system
    if context.args:
        inviter = int(context.args[0])
        cur.execute("SELECT invited_by FROM users WHERE user_id=?", (uid,))
        r = cur.fetchone()
        if not r:
            cur.execute(
                "INSERT INTO users (user_id, balance, invited_by) VALUES (?,?,?)",
                (uid, 5, inviter)
            )
            add_balance(inviter, 5)
            db.commit()

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📤 Send SMS", callback_data="send")],
        [InlineKeyboardButton("💰 My Balance", callback_data="balance")],
        [InlineKeyboardButton("🎁 Invite & Earn", callback_data="invite")],
    ])

    await update.message.reply_text(
        "🤖 Extreme Custom SMS Bot\n\nChoose option:",
        reply_markup=kb
    )

# ================= USER BUTTONS =================
async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    uid = q.from_user.id

    if q.data == "balance":
        await q.edit_message_text(f"💰 Your balance: {get_balance(uid)} SMS")

    elif q.data == "invite":
        link = f"https://t.me/{context.bot.username}?start={uid}"
        await q.edit_message_text(
            f"🎁 Invite & Earn\n\n"
            f"Per invite = 5 balance\n\n"
            f"🔗 {link}"
        )

    elif q.data == "send":
        context.user_data["step"] = "number"
        await q.edit_message_text("📱 Enter phone number:")

# ================= STEP HANDLER =================
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    if not await force_join(update, context):
        return

    step = context.user_data.get("step")

    if step == "number":
        context.user_data["number"] = update.message.text
        context.user_data["step"] = "message"
        await update.message.reply_text("✉️ Enter message:")
        return

    if step == "message":
        if get_balance(uid) <= 0:
            await update.message.reply_text("❌ Balance শেষ")
            context.user_data.clear()
            return

        number = context.user_data["number"]
        message = update.message.text

        params = {
            "apiKey": SMS_API_KEY,
            "senderId": SENDER_ID,
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

        context.user_data.clear()

# ================= ADMIN =================
async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Analytics", callback_data="analytics")],
        [InlineKeyboardButton("📄 Export Logs", callback_data="export")],
    ])
    await update.message.reply_text("👑 Admin Panel", reply_markup=kb)

async def admin_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    if q.from_user.id != ADMIN_ID:
        return

    if q.data == "analytics":
        today = datetime.now().strftime("%Y-%m-%d")
        week = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

        cur.execute("SELECT COUNT(*) FROM sms_logs WHERE time LIKE ?", (f"{today}%",))
        daily = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM sms_logs WHERE time >= ?", (week,))
        weekly = cur.fetchone()[0]

        await q.edit_message_text(
            f"📊 Analytics\n\n"
            f"📅 Today: {daily}\n"
            f"📈 Weekly: {weekly}"
        )

    elif q.data == "export":
        cur.execute("SELECT * FROM sms_logs")
        rows = cur.fetchall()

        with open("sms_logs.csv", "w", encoding="utf-8") as f:
            f.write("id,user_id,number,message,time\n")
            for r in rows:
                f.write(",".join([str(x) for x in r]) + "\n")

        await q.edit_message_text("📄 sms_logs.csv generated")

# ================= MAIN =================
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CallbackQueryHandler(buttons, pattern="^(send|balance|invite)$"))
    app.add_handler(CallbackQueryHandler(admin_buttons))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    print("🤖 Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
