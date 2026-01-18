# ===============================
# EXTREME CUSTOM SMS BOT – FINAL
# Button Only | Stable | SQLite
# ===============================

import sqlite3
import time
import requests
import asyncio
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
CHANNEL = "@ExtremeLevelTech"

SMS_API = "http://sms.greenheritageit.com/smsapi"
SMS_API_KEY = "$2y$10$8cKMTQTz6E0hdmbghuOjS.NLPWxolWv99uTlHoLC5VCXWq//Wk1D277"
SENDER_ID = "MultiSports"
TRANSACTION_TYPE = "TransactionType"
CAMPAIGN_ID = "campaignId"

DEFAULT_BALANCE = 10
REF_BONUS = 5
DAILY_BONUS = 2
DAY_SECONDS = 86400

# ================= DATABASE =================
db = sqlite3.connect("bot.db", check_same_thread=False)
c = db.cursor()

c.execute("""
CREATE TABLE IF NOT EXISTS users(
    user_id INTEGER PRIMARY KEY,
    balance INTEGER,
    ref_by INTEGER,
    ref_count INTEGER,
    banned INTEGER
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS sms(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    number TEXT,
    message TEXT,
    ts INTEGER
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS daily_bonus(
    user_id INTEGER PRIMARY KEY,
    last_claim INTEGER
)
""")

db.commit()

# ================= STATES =================
sms_state = {}
admin_state = {}

# ================= HELPERS =================
def get_user(uid):
    c.execute("SELECT * FROM users WHERE user_id=?", (uid,))
    return c.fetchone()

def add_user(uid, ref=None):
    if not get_user(uid):
        c.execute(
            "INSERT INTO users VALUES (?,?,?,?,?)",
            (uid, DEFAULT_BALANCE, ref, 0, 0)
        )
        if ref:
            c.execute("UPDATE users SET balance = balance + ?, ref_count = ref_count + 1 WHERE user_id=?",
                      (REF_BONUS, ref))
        db.commit()

def is_admin(uid):
    return uid == ADMIN_ID

# ================= MENUS =================
def user_menu():
    return ReplyKeyboardMarkup(
        [
            ["📩 Send SMS", "👤 My Profile"],
            ["👥 Invite", "🎁 Daily Bonus"],
            ["📊 My Referrals", "🏆 Leaderboard"],
            ["📜 SMS History", "🆘 Support"],
            ["⚙️ Admin Panel"]
        ],
        resize_keyboard=True
    )

def admin_menu():
    return ReplyKeyboardMarkup(
        [
            ["➕ Add Balance", "🔍 Check User"],
            ["🚫 Ban User", "✅ Unban User"],
            ["📢 Broadcast", "📊 Bot Stats"],
            ["⬅ Back"]
        ],
        resize_keyboard=True
    )

# ================= FORCE JOIN =================
async def force_join(update, context):
    try:
        m = await context.bot.get_chat_member(CHANNEL, update.effective_user.id)
        if m.status in ["member", "administrator", "creator"]:
            return True
    except:
        pass

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{CHANNEL[1:]}")],
        [InlineKeyboardButton("✅ Verify", callback_data="verify")]
    ])
    await update.message.reply_text("❌ Join channel first", reply_markup=kb)
    return False

# ================= TEXT HANDLER =================
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text

    if not get_user(uid):
        args = context.args if context.args else []
        ref = int(args[0]) if args and args[0].isdigit() else None
        add_user(uid, ref)

    # START
    if text == "/start":
        if not await force_join(update, context):
            return
        await update.message.reply_text("✅ Bot Ready", reply_markup=user_menu())
        return

    # SUPPORT
    if text == "🆘 Support":
        await update.message.reply_text("🆘 Support: @RexeTheRaka")
        return

    # ================= USER =================
    if text == "👤 My Profile":
        u = get_user(uid)
        await update.message.reply_text(
            f"👤 ID: {uid}\n💰 Balance: {u[1]}\n👥 Referrals: {u[3]}"
        )

    elif text == "👥 Invite":
        link = f"https://t.me/{context.bot.username}?start={uid}"
        await update.message.reply_text(f"{link}\n🎁 +5 Balance per referral")

    elif text == "🎁 Daily Bonus":
        c.execute("SELECT last_claim FROM daily_bonus WHERE user_id=?", (uid,))
        r = c.fetchone()
        now = int(time.time())
        if r and now - r[0] < DAY_SECONDS:
            await update.message.reply_text("⏳ Already claimed today")
        else:
            c.execute("INSERT OR REPLACE INTO daily_bonus VALUES (?,?)", (uid, now))
            c.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (DAILY_BONUS, uid))
            db.commit()
            await update.message.reply_text(f"🎁 Daily Bonus +{DAILY_BONUS}")

    elif text == "📊 My Referrals":
        u = get_user(uid)
        await update.message.reply_text(f"👥 Total Referrals: {u[3]}")

    elif text == "🏆 Leaderboard":
        c.execute("SELECT user_id, ref_count FROM users ORDER BY ref_count DESC LIMIT 10")
        rows = c.fetchall()
        msg = "🏆 Leaderboard\n\n"
        for i, (u, r) in enumerate(rows, 1):
            msg += f"{i}. {u} → {r}\n"
        await update.message.reply_text(msg)

    elif text == "📜 SMS History":
        c.execute("SELECT number,message FROM sms WHERE user_id=? ORDER BY id DESC LIMIT 5", (uid,))
        rows = c.fetchall()
        if not rows:
            await update.message.reply_text("No SMS history")
        else:
            msg = "📜 Last SMS:\n\n"
            for n, m in rows:
                msg += f"{n}\n{m}\n---\n"
            await update.message.reply_text(msg)

    # ================= SEND SMS =================
    elif text == "📩 Send SMS":
        if get_user(uid)[4] == 1:
            await update.message.reply_text("🚫 You are banned")
            return
        sms_state[uid] = {"step": "number"}
        await update.message.reply_text("📱 Enter phone number:")

    elif uid in sms_state:
        step = sms_state[uid]["step"]

        if step == "number":
            sms_state[uid]["number"] = text
            sms_state[uid]["step"] = "message"
            await update.message.reply_text("✉️ Enter message:")
            return

        if step == "message":
            number = sms_state[uid]["number"]
            message = text
            u = get_user(uid)

            if u[1] <= 0:
                await update.message.reply_text("❌ No balance")
                sms_state.pop(uid)
                return

            params = {
                "apiKey": SMS_API_KEY,
                "senderId": SENDER_ID,
                "transactionType": TRANSACTION_TYPE,
                "campaignId": CAMPAIGN_ID,
                "mobileNo": number,
                "message": message
            }

            try:
                r = requests.get(SMS_API, params=params, timeout=10)
                if r.status_code == 200:
                    c.execute("UPDATE users SET balance = balance - 1 WHERE user_id=?", (uid,))
                    c.execute("INSERT INTO sms VALUES (NULL,?,?,?)", (uid, number, message, int(time.time())))
                    db.commit()
                    await update.message.reply_text("✅ SMS Sent")
                else:
                    await update.message.reply_text("❌ SMS Failed")
            except:
                await update.message.reply_text("❌ API Error")

            sms_state.pop(uid)

    # ================= ADMIN =================
    elif text == "⚙️ Admin Panel" and is_admin(uid):
        await update.message.reply_text("⚙️ Admin Panel", reply_markup=admin_menu())

    elif text == "📊 Bot Stats" and is_admin(uid):
        c.execute("SELECT COUNT(*) FROM users")
        users = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM sms")
        sms_count = c.fetchone()[0]
        await update.message.reply_text(f"📊 Users: {users}\n📩 SMS Sent: {sms_count}")

    elif text == "⬅ Back" and is_admin(uid):
        await update.message.reply_text("Back to menu", reply_markup=user_menu())

# ================= VERIFY =================
async def verify_cb(update, context):
    q = update.callback_query
    await q.answer()
    await q.message.reply_text("✅ Verified", reply_markup=user_menu())

# ================= MAIN =================
async def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    app.add_handler(CallbackQueryHandler(verify_cb, pattern="verify"))
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
