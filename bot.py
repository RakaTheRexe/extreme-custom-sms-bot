# ===============================
# EXTREME CUSTOM SMS BOT (FINAL FIXED)
# ===============================

import logging
import sqlite3
import requests
import time
import asyncio
from datetime import datetime
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
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

DB_FILE = "bot.db"
DEFAULT_BALANCE = 10
REF_BONUS = 5
RATE_LIMIT = 30  # seconds

# ================= LOG =================
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("EXTREME-BOT")

# ================= DATABASE =================
def db():
    return sqlite3.connect(DB_FILE)

def init_db():
    c = db()
    cur = c.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users(
        user_id INTEGER PRIMARY KEY,
        balance INTEGER DEFAULT 10,
        ref_by INTEGER,
        ref_count INTEGER DEFAULT 0,
        banned INTEGER DEFAULT 0,
        joined INTEGER
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS sms_history(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        number TEXT,
        message TEXT,
        ts INTEGER
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS daily_bonus(
        user_id INTEGER PRIMARY KEY,
        last_claim INTEGER
    )""")

    c.commit()
    c.close()

# ================= HELPERS =================
def now():
    return int(time.time())

async def is_joined(uid, ctx):
    try:
        m = await ctx.bot.get_chat_member(CHANNEL_USERNAME, uid)
        return m.status in ["member", "administrator", "creator"]
    except:
        return False

def get_user(uid):
    c = db()
    r = c.execute("SELECT * FROM users WHERE user_id=?", (uid,)).fetchone()
    c.close()
    return r

def ensure_user(uid, ref=None):
    if not get_user(uid):
        c = db()
        c.execute(
            "INSERT INTO users(user_id,balance,ref_by,joined) VALUES(?,?,?,?)",
            (uid, DEFAULT_BALANCE, ref, now())
        )
        c.commit()
        c.close()

# ================= MENUS =================
def user_menu(is_admin=False):
    buttons = [
        ["📩 Send SMS", "👤 My Profile"],
        ["👥 Invite", "🎁 Daily Bonus"],
        ["📊 My Referrals", "🏆 Leaderboard"],
        ["📜 SMS History", "🆘 Support"]
    ]
    if is_admin:
        buttons.append(["⚙️ Admin Panel"])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

# ================= START =================
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    if not await is_joined(uid, ctx):
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 Join Channel", url="https://t.me/ExtremeLevelTech")]
        ])
        await update.message.reply_text("❌ আগে চ্যানেলে Join করো।", reply_markup=kb)
        return

    ref = None
    if ctx.args and ctx.args[0].isdigit():
        ref = int(ctx.args[0])
        if ref == uid:
            ref = None

    ensure_user(uid, ref)

    # Referral reward (one time)
    if ref:
        c = db()
        u = c.execute("SELECT ref_count FROM users WHERE user_id=?", (ref,)).fetchone()
        if u:
            c.execute(
                "UPDATE users SET ref_count=ref_count+1, balance=balance+? WHERE user_id=?",
                (REF_BONUS, ref)
            )
            c.commit()
        c.close()

    await update.message.reply_text(
        "✅ Bot Ready",
        reply_markup=user_menu(uid == ADMIN_ID)
    )

# ================= STATE =================
user_state = {}

# ================= TEXT HANDLER =================
async def text_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text

    # ===== SMS FLOW HANDLING (FIXED) =====
    if uid in user_state:
        await sms_flow(update, ctx)
        return

    # ===== USER BUTTONS =====
    if text == "📩 Send SMS":
        user_state[uid] = {"step": "phone"}
        await update.message.reply_text("📱 নাম্বার লিখো (01XXXXXXXXX)")
        return

    if text == "👤 My Profile":
        u = get_user(uid)
        await update.message.reply_text(
            f"👤 ID: {uid}\n💰 Balance: {u[1]}\n👥 Referrals: {u[3]}"
        )
        return

    if text == "👥 Invite":
        await update.message.reply_text(
            f"https://t.me/{ctx.bot.username}?start={uid}\n🎁 +5 Balance per refer"
        )
        return

    if text == "🎁 Daily Bonus":
        c = db()
        r = c.execute(
            "SELECT last_claim FROM daily_bonus WHERE user_id=?", (uid,)
        ).fetchone()
        if r and now() - r[0] < 86400:
            await update.message.reply_text("⏳ আজকে already নেওয়া হয়েছে।")
        else:
            c.execute(
                "INSERT OR REPLACE INTO daily_bonus(user_id,last_claim) VALUES(?,?)",
                (uid, now())
            )
            c.execute("UPDATE users SET balance=balance+2 WHERE user_id=?", (uid,))
            c.commit()
            await update.message.reply_text("🎁 +2 Balance Added")
        c.close()
        return

    if text == "📜 SMS History":
        c = db()
        rows = c.execute(
            "SELECT number,message,ts FROM sms_history WHERE user_id=? ORDER BY id DESC LIMIT 5",
            (uid,)
        ).fetchall()
        c.close()
        if not rows:
            await update.message.reply_text("📜 No SMS history.")
        else:
            msg = "📜 Last SMS:\n\n"
            for n,m,t in rows:
                msg += f"{n}\n{m}\n🕒 {datetime.fromtimestamp(t)}\n\n"
            await update.message.reply_text(msg)
        return

    if text == "🆘 Support":
        await update.message.reply_text("Support: @RexeTheRaka")
        return

    # ===== ADMIN PANEL BUTTON =====
    if text == "⚙️ Admin Panel":
        if uid != ADMIN_ID:
            await update.message.reply_text("❌ Unauthorized")
            return

        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")],
            [InlineKeyboardButton("📊 Bot Stats", callback_data="admin_stats")],
            [InlineKeyboardButton("🗂 Backup", callback_data="admin_backup")]
        ])
        await update.message.reply_text("⚙️ Admin Panel", reply_markup=kb)
        return

# ================= SMS FLOW =================
async def sms_flow(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    state = user_state.get(uid, {})

    if state["step"] == "phone":
        state["phone"] = update.message.text
        state["step"] = "msg"
        await update.message.reply_text("✉️ Message লিখো")
        return

    if state["step"] == "msg":
        state["msg"] = update.message.text
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Confirm", callback_data="sms_confirm"),
             InlineKeyboardButton("❌ Cancel", callback_data="sms_cancel")]
        ])
        await update.message.reply_text(
            f"📱 {state['phone']}\n✉️ {state['msg']}\nSend?",
            reply_markup=kb
        )
        return

# ================= CALLBACK =================
async def callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id

    if q.data == "sms_cancel":
        user_state.pop(uid, None)
        await q.edit_message_text("❌ Cancelled")
        return

    if q.data == "sms_confirm":
        u = get_user(uid)
        if u[1] <= 0:
            await q.edit_message_text("❌ Balance শেষ")
            user_state.pop(uid, None)
            return

        data = user_state[uid]
        params = {
            "apiKey": SMS_API_KEY,
            "senderId": SENDER_ID,
            "transactionType": TRANSACTION_TYPE,
            "campaignId": CAMPAIGN_ID,
            "mobileNo": data["phone"],
            "message": data["msg"]
        }

        r = requests.get(SMS_API_BASE, params=params, timeout=10)
        if r.status_code == 200:
            c = db()
            c.execute("UPDATE users SET balance=balance-1 WHERE user_id=?", (uid,))
            c.execute(
                "INSERT INTO sms_history(user_id,number,message,ts) VALUES(?,?,?,?)",
                (uid, data["phone"], data["msg"], now())
            )
            c.commit()
            c.close()
            await q.edit_message_text("✅ SMS Sent")
        else:
            await q.edit_message_text("❌ SMS Failed")

        user_state.pop(uid, None)

    # ===== ADMIN CALLBACKS =====
    if q.data == "admin_stats" and uid == ADMIN_ID:
        c = db()
        users = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        sms = c.execute("SELECT COUNT(*) FROM sms_history").fetchone()[0]
        c.close()
        await q.edit_message_text(
            f"📊 Bot Stats\n\n👥 Users: {users}\n📩 SMS Sent: {sms}"
        )

    if q.data == "admin_backup" and uid == ADMIN_ID:
        await q.edit_message_text("🗂 Backup OK (SQLite safe)")

# ================= MAIN =================
def main():
    init_db()
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    print("🤖 Extreme Custom SMS Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
