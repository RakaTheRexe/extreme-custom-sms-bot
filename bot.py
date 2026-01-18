# ===============================
# EXTREME CUSTOM SMS BOT (FINAL)
# ===============================

import logging, sqlite3, requests, asyncio, time
from datetime import datetime, timedelta
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder, ContextTypes,
    CallbackQueryHandler, MessageHandler, CommandHandler, ConversationHandler, filters
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

DB = "bot.db"
RATE_LIMIT = 30
DEFAULT_BALANCE = 10
REF_BONUS = 5

PHONE, MESSAGE, CONFIRM = range(3)

# ================= LOG =================
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("EXTREME-BOT")

# ================= DATABASE =================
def db_conn():
    return sqlite3.connect(DB)

def init_db():
    c = db_conn()
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

    cur.execute("""
    CREATE TABLE IF NOT EXISTS milestones(
        level INTEGER PRIMARY KEY,
        bonus INTEGER
    )""")

    for k,v in {5:20,10:50,20:80,30:120,40:150,50:200}.items():
        cur.execute("INSERT OR IGNORE INTO milestones VALUES(?,?)",(k,v))

    c.commit()
    c.close()

# ================= HELPERS =================
def now(): return int(time.time())

async def is_joined(uid, ctx):
    try:
        m = await ctx.bot.get_chat_member(CHANNEL_USERNAME, uid)
        return m.status in ["member","administrator","creator"]
    except:
        return False

def user(uid):
    c = db_conn()
    r = c.execute("SELECT * FROM users WHERE user_id=?", (uid,)).fetchone()
    c.close()
    return r

def ensure_user(uid, ref=None):
    if not user(uid):
        c = db_conn()
        c.execute(
            "INSERT INTO users(user_id,balance,ref_by,joined) VALUES(?,?,?,?)",
            (uid, DEFAULT_BALANCE, ref, now())
        )
        c.commit()
        c.close()

# ================= MENUS =================
def user_menu():
    return ReplyKeyboardMarkup([
        ["📩 Send SMS","👤 My Profile"],
        ["👥 Invite","🎁 Daily Bonus"],
        ["📊 My Referrals","🏆 Leaderboard"],
        ["📜 SMS History","🆘 Support"]
    ], resize_keyboard=True)

def admin_btn():
    return ReplyKeyboardMarkup([["⚙️ Admin Panel"]], resize_keyboard=True)

# ================= START =================
async def start(update:Update, ctx:ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not await is_joined(uid, ctx):
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 Join Channel", url="https://t.me/ExtremeLevelTech")]
        ])
        await update.message.reply_text("❌ Join channel first.", reply_markup=kb)
        return

    ref = None
    if ctx.args and ctx.args[0].isdigit():
        ref = int(ctx.args[0])
        if ref == uid: ref = None

    ensure_user(uid, ref)

    if ref:
        c = db_conn()
        r = c.execute("SELECT ref_count FROM users WHERE user_id=?", (ref,)).fetchone()
        if r:
            c.execute("UPDATE users SET ref_count=ref_count+1, balance=balance+? WHERE user_id=?",(REF_BONUS,ref))
            c.commit()
        c.close()

    await update.message.reply_text("✅ Bot Ready", reply_markup=user_menu())

# ================= USER BUTTON HANDLER =================
async def text_handler(update, ctx):
    uid = update.effective_user.id
    txt = update.message.text

    if txt=="🆘 Support":
        await update.message.reply_text("Contact: @RexeTheRaka"); return

    if txt=="👤 My Profile":
        u = user(uid)
        await update.message.reply_text(
            f"👤 ID: {uid}\n💰 Balance: {u[1]}\n👥 Referrals: {u[3]}"
        ); return

    if txt=="👥 Invite":
        await update.message.reply_text(
            f"https://t.me/{ctx.bot.username}?start={uid}\n+5 per refer"
        ); return

    if txt=="🎁 Daily Bonus":
        c=db_conn()
        r=c.execute("SELECT last_claim FROM daily_bonus WHERE user_id=?", (uid,)).fetchone()
        if r and now()-r[0]<86400:
            await update.message.reply_text("⏳ Already claimed today.")
        else:
            c.execute("INSERT OR REPLACE INTO daily_bonus VALUES(?,?)",(uid,now()))
            c.execute("UPDATE users SET balance=balance+2 WHERE user_id=?", (uid,))
            c.commit()
            await update.message.reply_text("🎁 +2 Balance Added")
        c.close()
        return

    if txt=="📩 Send SMS":
        ctx.user_data.clear()
        await update.message.reply_text("📱 Enter number:")
        ctx.user_data["step"]="phone"
        return

# ================= SMS FLOW =================
async def sms_flow(update, ctx):
    uid = update.effective_user.id
    step = ctx.user_data.get("step")

    if step=="phone":
        ctx.user_data["phone"]=update.message.text
        ctx.user_data["step"]="msg"
        await update.message.reply_text("✉️ Enter message:")
        return

    if step=="msg":
        ctx.user_data["msg"]=update.message.text
        kb=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Confirm",callback_data="send"),
             InlineKeyboardButton("❌ Cancel",callback_data="cancel")]
        ])
        await update.message.reply_text(
            f"{ctx.user_data['phone']}\n{ctx.user_data['msg']}",
            reply_markup=kb
        )

# ================= CALLBACK =================
async def cb(update, ctx):
    q=update.callback_query
    await q.answer()
    uid=q.from_user.id

    if q.data=="cancel":
        await q.edit_message_text("❌ Cancelled")
        return

    if q.data=="send":
        u=user(uid)
        if u[1]<=0:
            await q.edit_message_text("❌ No balance")
            return

        params={
            "apiKey":SMS_API_KEY,
            "senderId":SENDER_ID,
            "transactionType":TRANSACTION_TYPE,
            "campaignId":CAMPAIGN_ID,
            "mobileNo":ctx.user_data["phone"],
            "message":ctx.user_data["msg"]
        }
        r=requests.get(SMS_API_BASE,params=params,timeout=10)
        if r.status_code==200:
            c=db_conn()
            c.execute("UPDATE users SET balance=balance-1 WHERE user_id=?", (uid,))
            c.execute(
                "INSERT INTO sms_history(user_id,number,message,ts) VALUES(?,?,?,?)",
                (uid,ctx.user_data["phone"],ctx.user_data["msg"],now())
            )
            c.commit(); c.close()
            await q.edit_message_text("✅ SMS Sent")
        else:
            await q.edit_message_text("❌ Failed")

# ================= MAIN =================
def main():
    init_db()
    app=ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(cb))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, sms_flow))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    app.run_polling()

if __name__=="__main__":
    main()
