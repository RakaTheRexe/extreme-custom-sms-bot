import logging
import sqlite3
import requests
import asyncio
import nest_asyncio
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
    MessageHandler,
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

DEFAULT_BALANCE = 10
REF_BONUS = 5

# ================= DATABASE =================
db = sqlite3.connect("bot.db", check_same_thread=False)
cursor = db.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    balance INTEGER,
    referred_by INTEGER
)
""")
db.commit()

def get_user(uid):
    cursor.execute("SELECT * FROM users WHERE user_id=?", (uid,))
    return cursor.fetchone()

def add_user(uid, ref=None):
    if not get_user(uid):
        cursor.execute(
            "INSERT INTO users (user_id, balance, referred_by) VALUES (?, ?, ?)",
            (uid, DEFAULT_BALANCE, ref)
        )
        db.commit()

def update_balance(uid, amount):
    cursor.execute(
        "UPDATE users SET balance = balance + ? WHERE user_id=?",
        (amount, uid)
    )
    db.commit()

# ================= STATE =================
user_states = {}

# ================= LOG =================
logging.basicConfig(level=logging.INFO)
nest_asyncio.apply()

# ================= FORCE JOIN =================
async def force_join(update, context):
    uid = update.effective_user.id
    try:
        member = await context.bot.get_chat_member(CHANNEL_USERNAME, uid)
        if member.status in ["member", "administrator", "creator"]:
            return True
    except:
        pass

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Join Channel", url="https://t.me/ExtremeLevelTech")],
        [InlineKeyboardButton("✅ Verify", callback_data="verify")]
    ])

    await update.effective_chat.send_message(
        "❌ বট ব্যবহার করতে হলে আগে চ্যানেলে Join করতে হবে",
        reply_markup=keyboard
    )
    return False

async def verify(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    try:
        member = await context.bot.get_chat_member(CHANNEL_USERNAME, q.from_user.id)
        if member.status in ["member", "administrator", "creator"]:
            await q.edit_message_text("✅ Verify সফল! এখন /start লিখুন")
            return
    except:
        pass
    await q.edit_message_text("❌ এখনো Join করা হয়নি")

# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await force_join(update, context):
        return

    uid = update.effective_user.id

    if context.args:
        ref = int(context.args[0])
        if ref != uid and not get_user(uid):
            add_user(uid, ref)
            update_balance(ref, REF_BONUS)
    else:
        add_user(uid)

    keyboard = ReplyKeyboardMarkup(
        [["📩 Send SMS", "💰 Balance"], ["👥 Invite"]],
        resize_keyboard=True
    )

    await update.message.reply_text(
        "🤖 Extreme Custom SMS Bot Ready",
        reply_markup=keyboard
    )

# ================= BALANCE =================
async def balance(update, context):
    if not await force_join(update, context):
        return
    user = get_user(update.effective_user.id)
    await update.message.reply_text(f"💰 আপনার ব্যালেন্স: {user[1]} SMS")

# ================= INVITE =================
async def invite(update, context):
    if not await force_join(update, context):
        return
    uid = update.effective_user.id
    link = f"https://t.me/{context.bot.username}?start={uid}"
    await update.message.reply_text(
        f"👥 Invite Link:\n{link}\n\n🎁 প্রতি রেফারে +{REF_BONUS} SMS"
    )

# ================= SMS FLOW =================
async def start_sms_flow(update, context):
    user_states[update.effective_user.id] = {"step": "number"}
    await update.message.reply_text(
        "📱 যে নাম্বারে SMS পাঠাতে চাও সেটা পাঠাও\nউদাহরণ:\n01XXXXXXXX"
    )

async def text_handler(update, context):
    # 🔒 FORCE JOIN FOR ALL BUTTONS
    if not await force_join(update, context):
        return

    uid = update.effective_user.id
    text = update.message.text

    if text == "📩 Send SMS":
        await start_sms_flow(update, context)
        return

    if text == "💰 Balance":
        await balance(update, context)
        return

    if text == "👥 Invite":
        await invite(update, context)
        return

    if uid in user_states:
        state = user_states[uid]

        if state["step"] == "number":
            state["number"] = text
            state["step"] = "message"
            await update.message.reply_text("✉️ এখন SMS মেসেজ লিখো")
            return

        if state["step"] == "message":
            state["message"] = text
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✅ Confirm", callback_data="confirm_sms"),
                    InlineKeyboardButton("❌ Cancel", callback_data="cancel_sms")
                ]
            ])
            await update.message.reply_text(
                f"📱 Number: {state['number']}\n"
                f"✉️ Message:\n{state['message']}\n\nConfirm করো:",
                reply_markup=keyboard
            )

# ================= SMS CONFIRM =================
async def sms_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id

    # 🔒 FORCE JOIN AGAIN
    try:
        member = await context.bot.get_chat_member(CHANNEL_USERNAME, uid)
        if member.status not in ["member", "administrator", "creator"]:
            await q.edit_message_text("❌ আগে চ্যানেলে Join করতে হবে")
            return
    except:
        await q.edit_message_text("❌ আগে চ্যানেলে Join করতে হবে")
        return

    if uid not in user_states:
        await q.edit_message_text("❌ Session expired")
        return

    if q.data == "cancel_sms":
        user_states.pop(uid)
        await q.edit_message_text("❌ SMS বাতিল করা হয়েছে")
        return

    user = get_user(uid)
    if user[1] <= 0:
        await q.edit_message_text("❌ ব্যালেন্স শেষ")
        user_states.pop(uid)
        return

    data = user_states[uid]
    params = {
        "apiKey": SMS_API_KEY,
        "senderId": SENDER_ID,
        "transactionType": TRANSACTION_TYPE,
        "campaignId": CAMPAIGN_ID,
        "mobileNo": data["number"],
        "message": data["message"]
    }

    try:
        r = requests.get(SMS_API_BASE, params=params, timeout=15)
        if r.status_code == 200:
            update_balance(uid, -1)
            await q.edit_message_text("✅ SMS পাঠানো হয়েছে")
        else:
            await q.edit_message_text("❌ SMS পাঠানো যায়নি")
    except Exception as e:
        await q.edit_message_text(f"❌ Error: {e}")

    user_states.pop(uid)

# ================= ADMIN =================
async def admin(update, context):
    if update.effective_user.id != ADMIN_ID:
        return
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("👤 Check Balance", callback_data="checkbal")],
        [InlineKeyboardButton("➕ Add Balance", callback_data="addbal")]
    ])
    await update.message.reply_text("⚙ Admin Panel", reply_markup=kb)

async def admin_cb(update, context):
    q = update.callback_query
    await q.answer()
    if q.data == "checkbal":
        await q.edit_message_text("Usage:\n/check user_id")
    elif q.data == "addbal":
        await q.edit_message_text("Usage:\n/addbalance user_id amount")

async def check(update, context):
    if update.effective_user.id != ADMIN_ID:
        return
    uid = int(context.args[0])
    user = get_user(uid)
    await update.message.reply_text(f"User {uid} Balance: {user[1]}")

async def addbalance(update, context):
    if update.effective_user.id != ADMIN_ID:
        return
    uid = int(context.args[0])
    amt = int(context.args[1])
    update_balance(uid, amt)
    await update.message.reply_text("✅ Balance Added")

# ================= MAIN =================
async def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("balance", balance))
    app.add_handler(CommandHandler("invite", invite))
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CommandHandler("check", check))
    app.add_handler(CommandHandler("addbalance", addbalance))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    app.add_handler(CallbackQueryHandler(verify, pattern="verify"))
    app.add_handler(CallbackQueryHandler(admin_cb, pattern="checkbal|addbal"))
    app.add_handler(CallbackQueryHandler(sms_confirm_callback, pattern="confirm_sms|cancel_sms"))

    print("Bot running...")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
