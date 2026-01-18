# ==========================================
# EXTREME CUSTOM SMS BOT – FINAL FIXED
# Button Only | Stable | SQLite | Tested
# ==========================================

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
    MessageHandler,
    CallbackQueryHandler,
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
    ref_count INTEGER,
    ref_by INTEGER,
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
            (uid, DEFAULT_BALANCE, 0, ref, 0)
        )
        if ref and get_user(ref):
            c.execute(
                "UPDATE users SET balance = balance + ?, ref_count = ref_count + 1 WHERE user_id=?",
                (REF_BONUS, ref)
            )
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
    text = update.message.text.strip()

    if not get_user(uid):
        ref = None
        if context.args and context.args[0].isdigit():
            ref = int(context.args[0])
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
            f"👤 ID: {uid}\n💰 Balance: {u[1]}\n👥 Referrals: {u[2]}"
        )
        return

    if text == "👥 Invite":
        link = f"https://t.me/{context.bot.username}?start={uid}"
        await update.message.reply_text(f"{link}\n🎁 +5 Balance per referral")
        return

    if text == "🎁 Daily Bonus":
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
        return

    if text == "📊 My Referrals":
        u = get_user(uid)
        await update.message.reply_text(f"👥 Total Referrals: {u[2]}")
        return

    if text == "🏆 Leaderboard":
        c.execute("SELECT user_id, ref_count FROM users ORDER BY ref_count DESC LIMIT 10")
        rows = c.fetchall()
        msg = "🏆 Leaderboard\n\n"
        for i, (u, r) in enumerate(rows, 1):
            msg += f"{i}. {u} → {r}\n"
        await update.message.reply_text(msg)
        return

    if text == "📜 SMS History":
        c.execute("SELECT number,message FROM sms WHERE user_id=? ORDER BY id DESC LIMIT 5", (uid,))
        rows = c.fetchall()
        if not rows:
            await update.message.reply_text("No SMS history")
        else:
            msg = "📜 Last SMS:\n\n"
            for n, m in rows:
                msg += f"{n}\n{m}\n---\n"
            await update.message.reply_text(msg)
        return

    # ================= SEND SMS =================
    if text == "📩 Send SMS":
        if get_user(uid)[4] == 1:
            await update.message.reply_text("🚫 You are banned")
            return
        sms_state[uid] = {"step": "number"}
        await update.message.reply_text("📱 Enter phone number:")
        return

    if uid in sms_state:
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
                    c.execute("INSERT INTO sms VALUES (NULL,?,?,?)", (uid, number, message))
                    db.commit()
                    await update.message.reply_text("✅ SMS Sent")
                else:
                    await update.message.reply_text("❌ SMS Failed")
            except:
                await update.message.reply_text("❌ API Error")

            sms_state.pop(uid)
            return

    # ================= ADMIN =================
    if text == "⚙️ Admin Panel" and is_admin(uid):
        await update.message.reply_text("⚙️ Admin Panel", reply_markup=admin_menu())
        return

    if is_admin(uid):

        if text == "➕ Add Balance":
            admin_state[uid] = {"action": "addbal"}
            await update.message.reply_text("Send: USER_ID AMOUNT")
            return

        if text == "🔍 Check User":
            admin_state[uid] = {"action": "check"}
            await update.message.reply_text("Send USER_ID")
            return

        if text == "🚫 Ban User":
            admin_state[uid] = {"action": "ban"}
            await update.message.reply_text("Send USER_ID")
            return

        if text == "✅ Unban User":
            admin_state[uid] = {"action": "unban"}
            await update.message.reply_text("Send USER_ID")
            return

        if text == "📢 Broadcast":
            admin_state[uid] = {"action": "broadcast"}
            await update.message.reply_text("Send broadcast message")
            return

        if text == "📊 Bot Stats":
            c.execute("SELECT COUNT(*) FROM users")
            users = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM sms")
            sms_count = c.fetchone()[0]
            await update.message.reply_text(
                f"📊 Bot Stats\n👥 Users: {users}\n📩 SMS Sent: {sms_count}"
            )
            return

        if text == "⬅ Back":
            await update.message.reply_text("Back", reply_markup=user_menu())
            return

        if uid in admin_state:
            action = admin_state[uid]["action"]

            if action == "addbal":
                try:
                    target, amount = map(int, text.split())
                    c.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (amount, target))
                    db.commit()
                    await update.message.reply_text(f"✅ Added {amount} to {target}")
                except:
                    await update.message.reply_text("❌ Format: USER_ID AMOUNT")

            elif action == "check":
                target = int(text)
                u = get_user(target)
                if u:
                    await update.message.reply_text(
                        f"👤 {target}\n💰 {u[1]}\n👥 {u[2]}\n🚫 Banned: {u[4]}"
                    )
                else:
                    await update.message.reply_text("❌ User not found")

            elif action == "ban":
                target = int(text)
                c.execute("UPDATE users SET banned=1 WHERE user_id=?", (target,))
                db.commit()
                await update.message.reply_text(f"🚫 User {target} banned")

            elif action == "unban":
                target = int(text)
                c.execute("UPDATE users SET banned=0 WHERE user_id=?", (target,))
                db.commit()
                await update.message.reply_text(f"✅ User {target} unbanned")

            elif action == "broadcast":
                c.execute("SELECT user_id FROM users")
                users = c.fetchall()
                sent = 0
                for u in users:
                    try:
                        await context.bot.send_message(u[0], f"📢 {text}")
                        sent += 1
                    except:
                        pass
                await update.message.reply_text(f"📢 Sent to {sent} users")

            admin_state.pop(uid)
            return

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
