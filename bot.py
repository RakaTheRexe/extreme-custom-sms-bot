# =========================================
# EXTREME CUSTOM SMS BOT (FINAL – STABLE)
# Button Only | Admin + User | SQLite
# =========================================

import sqlite3
import time
import requests
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    CallbackQueryHandler,
    filters
)

# ============== CONFIG ====================
BOT_TOKEN = "YOUR_BOT_TOKEN"
ADMIN_ID = 7008757477
CHANNEL = "@ExtremeLevelTech"

SMS_API_URL = "http://sms.greenheritageit.com/smsapi"
SMS_API_KEY = "YOUR_SMS_API_KEY"
SENDER_ID = "MultiSports"

DEFAULT_BALANCE = 10
REF_BONUS = 5
DAILY_BONUS = 2
DAY = 86400

# ============== DATABASE ==================
db = sqlite3.connect("bot.db", check_same_thread=False)
c = db.cursor()

c.execute("""
CREATE TABLE IF NOT EXISTS users(
    user_id INTEGER PRIMARY KEY,
    balance INTEGER,
    referrals INTEGER,
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
CREATE TABLE IF NOT EXISTS daily(
    user_id INTEGER PRIMARY KEY,
    last_claim INTEGER
)
""")

db.commit()

# ============== HELPERS ===================
def is_admin(uid):
    return uid == ADMIN_ID

def get_user(uid):
    c.execute("SELECT * FROM users WHERE user_id=?", (uid,))
    return c.fetchone()

def add_user(uid):
    if not get_user(uid):
        c.execute(
            "INSERT INTO users VALUES (?,?,?,?)",
            (uid, DEFAULT_BALANCE, 0, 0)
        )
        db.commit()

# ============== MENUS =====================
def user_menu():
    return ReplyKeyboardMarkup(
        [
            ["📩 Send SMS", "👤 My Profile"],
            ["👥 Invite", "🎁 Daily Bonus"],
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

# ============== FORCE JOIN ================
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
    await update.message.reply_text(
        "❌ Join channel first",
        reply_markup=kb
    )
    return False

# ============== STATES ====================
STATE = {}

# ============== TEXT HANDLER ==============
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text

    add_user(uid)

    if not await force_join(update, context):
        return

    # ---------- START ----------
    if text == "/start":
        await update.message.reply_text("✅ Bot Ready", reply_markup=user_menu())
        return

    # ---------- USER ----------
    if text == "👤 My Profile":
        u = get_user(uid)
        await update.message.reply_text(
            f"👤 ID: {uid}\n💰 Balance: {u[1]}\n👥 Referrals: {u[2]}"
        )

    elif text == "👥 Invite":
        link = f"https://t.me/{context.bot.username}?start={uid}"
        await update.message.reply_text(
            f"🔗 Invite Link:\n{link}\n🎁 +{REF_BONUS} Balance"
        )

    elif text == "🎁 Daily Bonus":
        now = int(time.time())
        c.execute("SELECT last_claim FROM daily WHERE user_id=?", (uid,))
        r = c.fetchone()

        if r and now - r[0] < DAY:
            await update.message.reply_text("⏳ Already claimed today")
        else:
            c.execute(
                "INSERT OR REPLACE INTO daily VALUES (?,?)",
                (uid, now)
            )
            c.execute(
                "UPDATE users SET balance = balance + ? WHERE user_id=?",
                (DAILY_BONUS, uid)
            )
            db.commit()
            await update.message.reply_text(
                f"🎁 Bonus Claimed! +{DAILY_BONUS}"
            )

    elif text == "📜 SMS History":
        c.execute(
            "SELECT number,message FROM sms WHERE user_id=? ORDER BY id DESC LIMIT 5",
            (uid,)
        )
        rows = c.fetchall()
        if not rows:
            await update.message.reply_text("No SMS history")
        else:
            msg = "📜 Last SMS:\n\n"
            for n, m in rows:
                msg += f"{n}\n{m}\n---\n"
            await update.message.reply_text(msg)

    elif text == "🆘 Support":
        await update.message.reply_text("Support: @RexeTheRaka")

    # ---------- ADMIN ----------
    elif text == "⚙️ Admin Panel" and is_admin(uid):
        await update.message.reply_text("⚙️ Admin Panel", reply_markup=admin_menu())

    elif text == "➕ Add Balance" and is_admin(uid):
        STATE[uid] = "ADD_BAL"
        await update.message.reply_text("Send: USER_ID AMOUNT")

    elif text == "🔍 Check User" and is_admin(uid):
        STATE[uid] = "CHECK"
        await update.message.reply_text("Send USER_ID")

    elif text == "🚫 Ban User" and is_admin(uid):
        STATE[uid] = "BAN"
        await update.message.reply_text("Send USER_ID")

    elif text == "✅ Unban User" and is_admin(uid):
        STATE[uid] = "UNBAN"
        await update.message.reply_text("Send USER_ID")

    elif text == "📢 Broadcast" and is_admin(uid):
        STATE[uid] = "BROADCAST"
        await update.message.reply_text("Send broadcast message")

    elif text == "📊 Bot Stats" and is_admin(uid):
        c.execute("SELECT COUNT(*) FROM users")
        users = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM sms")
        sms = c.fetchone()[0]
        await update.message.reply_text(
            f"📊 Stats\n👥 Users: {users}\n📩 SMS Sent: {sms}"
        )

    elif text == "⬅ Back" and is_admin(uid):
        await update.message.reply_text("Back", reply_markup=user_menu())

    # ---------- STATE HANDLING ----------
    elif uid in STATE:
        st = STATE.pop(uid)

        try:
            if st == "ADD_BAL":
                u, a = map(int, text.split())
                c.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (a, u))
                db.commit()
                await update.message.reply_text("✅ Balance Added")

            elif st == "CHECK":
                u = int(text)
                r = get_user(u)
                await update.message.reply_text(
                    f"ID: {u}\nBalance: {r[1]}\nBanned: {r[3]}"
                )

            elif st == "BAN":
                u = int(text)
                c.execute("UPDATE users SET banned=1 WHERE user_id=?", (u,))
                db.commit()
                await update.message.reply_text("🚫 User Banned")

            elif st == "UNBAN":
                u = int(text)
                c.execute("UPDATE users SET banned=0 WHERE user_id=?", (u,))
                db.commit()
                await update.message.reply_text("✅ User Unbanned")

            elif st == "BROADCAST":
                c.execute("SELECT user_id FROM users")
                for (u,) in c.fetchall():
                    try:
                        await context.bot.send_message(u, text)
                    except:
                        pass
                await update.message.reply_text("📢 Broadcast Sent")

        except:
            await update.message.reply_text("❌ Invalid input")

# ============== VERIFY ====================
async def verify_cb(update, context):
    await update.callback_query.answer()
    await update.callback_query.message.reply_text(
        "✅ Verified",
        reply_markup=user_menu()
    )

# ============== MAIN ======================
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT, text_handler))
    app.add_handler(CallbackQueryHandler(verify_cb, pattern="verify"))
    app.run_polling()

if __name__ == "__main__":
    main()
