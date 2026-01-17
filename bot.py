# ================= IMPORTS =================
import sqlite3, logging, requests, asyncio, threading
from datetime import datetime, date, timedelta
from flask import Flask, jsonify
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

# ================= BASIC CONFIG =================
BOT_TOKEN = "8345293297:AAHv6KfWaFsXJ-rlbJwupBqgTHbKt3CWS5U"
ADMIN_ID = 7008757477
CHANNEL = "@ExtremeLevelTech"

SMS_API_URL = "http://sms.greenheritageit.com/smsapi"
SMS_API_KEY = "$2y$10$8cKMTQTz6E0hdmbghuOjS.NLPWxolWv99uTlHoLC5VCXWq//Wk1D277"
SENDER_ID = "MultiSports"
TRANSACTION_TYPE = "TransactionType"
CAMPAIGN_ID = "campaignId"

INVITE_REWARD = 5

logging.basicConfig(level=logging.INFO)

# ================= DATABASE =================
db = sqlite3.connect("database.db", check_same_thread=False)
cur = db.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users(
    user_id INTEGER PRIMARY KEY,
    balance INTEGER DEFAULT 0,
    invited_by INTEGER,
    role TEXT DEFAULT 'user',
    banned INTEGER DEFAULT 0
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS sms_logs(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    number TEXT,
    message TEXT,
    time TEXT,
    day TEXT
)
""")
db.commit()

# ================= HELPERS =================
def is_admin(uid): return uid == ADMIN_ID
def is_reseller(uid):
    cur.execute("SELECT role FROM users WHERE user_id=?", (uid,))
    r = cur.fetchone()
    return r and r[0] in ["admin", "reseller"]

def get_balance(uid):
    cur.execute("SELECT balance FROM users WHERE user_id=?", (uid,))
    r = cur.fetchone()
    if not r:
        cur.execute("INSERT INTO users(user_id,balance) VALUES (?,0)", (uid,))
        db.commit()
        return 0
    return r[0]

def add_balance(uid, amt):
    cur.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (amt, uid))
    db.commit()

def is_banned(uid):
    cur.execute("SELECT banned FROM users WHERE user_id=?", (uid,))
    r = cur.fetchone()
    return r and r[0] == 1

# ================= FORCE JOIN =================
async def force_join(update, context):
    try:
        m = await context.bot.get_chat_member(CHANNEL, update.effective_user.id)
        return m.status in ["member","administrator","creator"]
    except:
        return False

# ================= START + INVITE =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    if context.args:
        ref = int(context.args[0])
        cur.execute("SELECT user_id FROM users WHERE user_id=?", (uid,))
        if not cur.fetchone():
            cur.execute("INSERT INTO users(user_id,invited_by) VALUES (?,?)", (uid, ref))
            add_balance(ref, INVITE_REWARD)
            db.commit()

    if not await force_join(update, context):
        await update.message.reply_text(f"Join first:\nhttps://t.me/{CHANNEL.replace('@','')}")
        return

    kb = [
        [InlineKeyboardButton("📨 Send SMS", callback_data="send")],
        [InlineKeyboardButton("💰 Balance", callback_data="bal"),
         InlineKeyboardButton("🎁 Invite", callback_data="invite")],
    ]
    if is_admin(uid):
        kb.append([InlineKeyboardButton("👑 Admin Panel", callback_data="admin")])

    await update.message.reply_text("🤖 Extreme SMS Bot", reply_markup=InlineKeyboardMarkup(kb))

# ================= USER BUTTONS =================
user_states = {}

async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id

    if q.data == "bal":
        await q.edit_message_text(f"💰 Balance: {get_balance(uid)}")

    elif q.data == "invite":
        await q.edit_message_text(
            f"🎁 Invite & Earn\n\n"
            f"Reward: {INVITE_REWARD} SMS\n\n"
            f"https://t.me/{context.bot.username}?start={uid}"
        )

    elif q.data == "send":
        if is_banned(uid):
            await q.edit_message_text("🚫 You are banned")
            return
        if get_balance(uid) <= 0:
            await q.edit_message_text("❌ Balance finished")
            return
        user_states[uid] = {"step":"number"}
        await q.edit_message_text("📱 Send number:")

    elif q.data == "admin":
        if not is_admin(uid): return
        kb = [
            [InlineKeyboardButton("➕ Add Balance", callback_data="addbal")],
            [InlineKeyboardButton("👥 Make Reseller", callback_data="reseller")],
            [InlineKeyboardButton("📊 Analytics", callback_data="stats")],
            [InlineKeyboardButton("🚫 Ban User", callback_data="ban")]
        ]
        await q.edit_message_text("👑 Admin Panel", reply_markup=InlineKeyboardMarkup(kb))

    elif q.data == "stats":
        today = date.today().isoformat()
        week = (date.today() - timedelta(days=7)).isoformat()
        cur.execute("SELECT COUNT(*) FROM sms_logs WHERE day=?", (today,))
        d = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM sms_logs WHERE day>=?", (week,))
        w = cur.fetchone()[0]
        await q.edit_message_text(f"📊 Analytics\n\nToday: {d}\nLast 7 days: {w}")

# ================= TEXT HANDLER (STEP SMS + ADMIN) =================
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    txt = update.message.text

    # USER SMS FLOW
    if uid in user_states:
        state = user_states[uid]
        if state["step"] == "number":
            state["number"] = txt
            state["step"] = "msg"
            await update.message.reply_text("✉️ Send message:")
            return
        if state["step"] == "msg":
            number = state["number"]
            msg = txt
            del user_states[uid]

            params = {
                "apiKey": SMS_API_KEY,
                "senderId": SENDER_ID,
                "transactionType": TRANSACTION_TYPE,
                "campaignId": CAMPAIGN_ID,
                "mobileNo": number,
                "message": msg
            }

            r = requests.get(SMS_API_URL, params=params)
            if r.status_code == 200:
                add_balance(uid, -1)
                cur.execute(
                    "INSERT INTO sms_logs(user_id,number,message,time,day) VALUES (?,?,?,?,?)",
                    (uid, number, msg, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), date.today().isoformat())
                )
                db.commit()
                await update.message.reply_text("✅ SMS Sent")
            else:
                await update.message.reply_text("❌ SMS Failed")
            return

    # ADMIN / RESELLER TEXT
    if is_admin(uid):
        parts = txt.split()
        if len(parts)==2:
            add_balance(int(parts[0]), int(parts[1]))
            await update.message.reply_text("✅ Balance added")
        elif len(parts)==1:
            cur.execute("UPDATE users SET banned=1 WHERE user_id=?", (int(parts[0]),))
            db.commit()
            await update.message.reply_text("🚫 User banned")

# ================= WEB DASHBOARD =================
app = Flask(__name__)

@app.route("/")
def dash():
    cur.execute("SELECT COUNT(*) FROM users")
    u = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM sms_logs")
    s = cur.fetchone()[0]
    return jsonify({"users":u,"sms_sent":s})

def run_web():
    app.run("0.0.0.0", 8080)

# ================= MAIN =================
async def main():
    threading.Thread(target=run_web).start()
    bot = ApplicationBuilder().token(BOT_TOKEN).build()
    bot.add_handler(CommandHandler("start", start))
    bot.add_handler(CallbackQueryHandler(buttons))
    bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    await bot.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
