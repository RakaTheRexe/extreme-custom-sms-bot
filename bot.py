import logging
import requests
import asyncio
import nest_asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler
)

# ================== CONFIG ==================
TELEGRAM_TOKEN = "8345293297:AAHv6KfWaFsXJ-rlbJwupBqgTHbKt3CWS5U"

ADMIN_ID = 7008757477
CHANNEL_USERNAME = "@ExtremeLevelTech"

SMS_API_BASE = "http://sms.greenheritageit.com/smsapi"
SMS_API_KEY = "$2y$10$8cKMTQTz6E0hdmbghuOjS.NLPWxolWv99uTlHoLC5VCXWq//Wk1D277"
SENDER_ID = "MultiSports"          # চাইলে বদলাতে পারো
TRANSACTION_TYPE = "TransactionType"
CAMPAIGN_ID = "campaignId"

# ================== MEMORY DB ==================
users = {}

def init_user(uid):
    if uid not in users:
        users[uid] = {
            "balance": 10   # default balance
        }

# ================== LOGGING ==================
logging.basicConfig(level=logging.INFO)
nest_asyncio.apply()

# ================== FORCE JOIN ==================
async def force_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="❌ বট ব্যবহার করতে হলে আগে চ্যানেলে জয়েন করুন",
        reply_markup=keyboard
    )
    return False

async def verify(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id

    try:
        member = await context.bot.get_chat_member(CHANNEL_USERNAME, uid)
        if member.status in ["member", "administrator", "creator"]:
            await query.edit_message_text("✅ Verify সফল! এখন /start লিখুন")
            return
    except:
        pass

    await query.edit_message_text("❌ এখনো জয়েন করা হয়নি")

# ================== COMMANDS ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await force_join(update, context):
        return

    uid = update.effective_user.id
    init_user(uid)

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=(
            "🤖 Extreme Custom SMS Bot\n\n"
            "📩 SMS পাঠাতে:\n"
            "/sms 01XXXXXXXX message\n\n"
            "💰 ব্যালেন্স দেখতে:\n"
            "/balance"
        )
    )

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    init_user(uid)

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"💰 আপনার ব্যালেন্স: {users[uid]['balance']} SMS"
    )

async def sms(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await force_join(update, context):
        return

    uid = update.effective_user.id
    init_user(uid)

    if users[uid]["balance"] <= 0:
        await context.bot.send_message(update.effective_chat.id, "❌ ব্যালেন্স শেষ")
        return

    args = context.args
    if len(args) < 2:
        await context.bot.send_message(
            update.effective_chat.id,
            "⚠️ ফরম্যাট:\n/sms 01XXXXXXXX message"
        )
        return

    number = args[0]
    message = " ".join(args[1:])

    params = {
        "apiKey": SMS_API_KEY,
        "senderId": SENDER_ID,
        "transactionType": TRANSACTION_TYPE,
        "campaignId": CAMPAIGN_ID,
        "mobileNo": number,
        "message": message
    }

    try:
        r = requests.get(SMS_API_BASE, params=params, timeout=15)

        if r.status_code == 200:
            users[uid]["balance"] -= 1
            await context.bot.send_message(
                update.effective_chat.id,
                f"✅ SMS পাঠানো হয়েছে\n📱 {number}\n💰 Remaining: {users[uid]['balance']}"
            )
        else:
            await context.bot.send_message(
                update.effective_chat.id,
                "❌ SMS পাঠানো যায়নি"
            )
    except Exception as e:
        await context.bot.send_message(
            update.effective_chat.id,
            f"❌ Error: {e}"
        )

# ================== ADMIN ==================
async def addbalance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    try:
        uid = int(context.args[0])
        amt = int(context.args[1])
        init_user(uid)
        users[uid]["balance"] += amt
        await context.bot.send_message(
            update.effective_chat.id,
            "✅ Balance added"
        )
    except:
        await context.bot.send_message(
            update.effective_chat.id,
            "Usage:\n/addbalance user_id amount"
        )

# ================== MAIN ==================
async def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("balance", balance))
    app.add_handler(CommandHandler("sms", sms))
    app.add_handler(CommandHandler("addbalance", addbalance))
    app.add_handler(CallbackQueryHandler(verify, pattern="verify"))

    print("Bot running...")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
