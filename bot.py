import sqlite3
import requests
from datetime import datetime

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

# ================= BOT CONFIG (HARDCODED) =================
BOT_TOKEN = "8345293297:AAHv6KfWaFsXJ-rlbJwupBqgTHbKt3CWS5U"
ADMIN_ID = 7008757477
CHANNEL = "@ExtremeLevelTech"

SMS_API_URL = "http://sms.greenheritageit.com/smsapi"
SMS_API_KEY = "$2y$10$8cKMTQTz6E0hdmbghuOjS.NLPWxolWv99uTlHoLC5VCXWq//Wk1D277"
SENDER_ID = "MultiSports"

INVITE_REWARD = 5

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
            f"❌ আগে Channel join করো:\nhttps://t.me/{CHANNEL.replace('@','')}"
        )
        return

    # Invite system
    if context.args:
        inviter = int(context.args[0])
        if inviter != uid:
            cur.execute("SELECT invited_by FROM users WHERE user_id=?", (uid,))
            r = cur.fetchone()
            if not r:
                cur.execute(
                    "INSERT INTO users (user_id, balance, invited_by) VALUES (?,?,?)",
                    (uid, 5, inviter)
                )
                add_balance(inviter, INVITE_REWARD)
                db.commit()

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📨 Send SMS", callback_data="send")],
        [InlineKeyboardButton("💰 Balance", callback_data="balance")],
        [InlineKeyboardButton("🎁 Invite", callback_data="invite")],
    ])
    await update.message.reply_text("🤖 Extreme Custom SMS Bot", reply_markup=kb)

# ================= BUTTON HANDLER =================
user_state = {}

async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id

    if q.data == "balance":
        await q.edit_message_text(f"💰 Balance: {get_balance(uid)}")

    elif q.data == "invite":
        link = f"https://t.me/{context.bot.username}?start={uid}"
        await q.edit_message_text(
            f"🎁 Invite & Earn\n\nPer invite = {INVITE_REWARD}\n\n{link}"
        )

    elif q.data == "send":
        if get_balance(uid) <= 0:
            await q.edit_message_text("❌ Balance শেষ")
            return
        user_state[uid] = {"step": "number"}
        await q.edit_message_text("📱 Number পাঠাও:")

# ================= SMS STEP FLOW =================
async def message_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in user_state:
        return

    state = user_state[uid]

    if state["step"] == "number":
        state["number"] = update.message.text
        state["step"] = "message"
        await update.message.reply_text("✉️ Message পাঠাও:")
        return

    if state["step"] == "message":
        if get_balance(uid) <= 0:
            await update.message.reply_text("❌ Balance শেষ")
            user_state.pop(uid)
            return

        number = state["number"]
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

        user_state.pop(uid)

# ================= ADMIN =================
async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("👤 User Balances", callback_data="userbal")],
        [InlineKeyboardButton("➕ Add Balance", callback_data="addbal")],
        [InlineKeyboardButton("📊 Export Logs", callback_data="export")],
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

    elif q.data == "addbal":
        await q.edit_message_text("Send: USER_ID AMOUNT")

    elif q.data == "export":
        cur.execute("SELECT * FROM sms_logs")
        rows = cur.fetchall()
        with open("sms_logs.csv", "w", encoding="utf-8") as f:
            f.write("id,user_id,number,message,time\n")
            for r in rows:
                f.write(",".join([str(x) for x in r]) + "\n")
        await q.edit_message_text("📊 Export ready (sms_logs.csv)")

# Admin text input (balance add)
async def admin_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    parts = update.message.text.split()
    if len(parts) == 2:
        uid = int(parts[0])
        amt = int(parts[1])
        add_balance(uid, amt)
        await update.message.reply_text("✅ Balance added")

# ================= MAIN =================
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CallbackQueryHandler(admin_buttons))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, admin_text))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_flow))

    print("🤖 Worker bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
