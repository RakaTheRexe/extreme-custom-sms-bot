import logging
import sqlite3
import requests
import asyncio
import os
from datetime import datetime, date
from telegram import (
    Update, 
    InlineKeyboardButton, 
    InlineKeyboardMarkup, 
    ReplyKeyboardMarkup, 
    KeyboardButton
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ConversationHandler
)

# ================== ⚙️ CONFIGURATION ==================
TELEGRAM_TOKEN = "8345293297:AAHv6KfWaFsXJ-rlbJwupBqgTHbKt3CWS5U"
ADMIN_ID = 7008757477
CHANNEL_USERNAME = "@ExtremeLevelTech" 
DEVELOPER_USERNAME = "@RexeTheRaka"
BOT_USERNAME = "extremecustomesms_bot" 

# SMS API CONFIG
SMS_API_BASE = "http://sms.greenheritageit.com/smsapi"
SMS_API_KEY = "$2y$10$8cKMTQTz6E0hdmbghuOjS.NLPWxolWv99uTlHoLC5VCXWq//Wk1D277"
SENDER_ID = "MultiSports"

# SYSTEM CONFIG
DB_FILE = "bot_database.db"
DAILY_BONUS_AMOUNT = 2
REFERRAL_REWARD = 5
MIN_SMS_COST = 1
RATE_LIMIT_SEC = 10 

# STATES
PHONE, MESSAGE, CONFIRM = range(3)
ADMIN_INPUT = range(1)

# ================== 📝 LOGGING ==================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ================== 🗄️ DATABASE MANAGER ==================
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        first_name TEXT,
        username TEXT,
        balance INTEGER DEFAULT 10,
        ref_count INTEGER DEFAULT 0,
        referrer_id INTEGER,
        join_date TEXT,
        last_bonus_date TEXT,
        is_banned INTEGER DEFAULT 0
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS sms_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        number TEXT,
        message TEXT,
        status TEXT,
        timestamp TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS milestone_claims (
        user_id INTEGER,
        level INTEGER
    )''')
    conn.commit()
    conn.close()

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

# ================== 🛡️ HELPER FUNCTIONS ==================
async def check_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    try:
        member = await context.bot.get_chat_member(CHANNEL_USERNAME, user_id)
        if member.status in ["member", "administrator", "creator"]:
            return True
    except:
        return True 
    
    keyboard = [[InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}")]]
    await context.bot.send_message(user_id, "⚠️ **বট ব্যবহার করতে হলে আমাদের চ্যানেলে জয়েন করুন।**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    return False

def get_badge(ref_count):
    if ref_count >= 50: return "🥇 Gold"
    if ref_count >= 20: return "🥈 Silver"
    if ref_count >= 10: return "🥉 Bronze"
    return "👤 Rookie"

def check_milestones(user_id, current_refs):
    milestones = {5: 20, 10: 50, 20: 80, 50: 200}
    conn = get_db()
    c = conn.cursor()
    total_bonus = 0
    for level, reward in milestones.items():
        if current_refs >= level:
            claimed = c.execute("SELECT 1 FROM milestone_claims WHERE user_id=? AND level=?", (user_id, level)).fetchone()
            if not claimed:
                c.execute("INSERT INTO milestone_claims (user_id, level) VALUES (?, ?)", (user_id, level))
                c.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (reward, user_id))
                total_bonus += reward
    conn.commit()
    conn.close()
    return total_bonus

# ================== 🚀 MAIN MENU (BUTTON BAR) ==================
async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    # Persistent Keyboard Layout (Button Bar)
    keyboard = [
        ["📩 Send SMS", "💰 Balance"],
        ["🎁 Daily Bonus", "👤 My Profile"],
        ["👥 Invite Friends", "🏆 Leaderboard"],
        ["📜 History", "🆘 Support"]
    ]
    
    if user.id == ADMIN_ID:
        keyboard.append(["⚙️ Admin Panel"])

    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
    
    text = (f"👋 **Hello {user.first_name}!**\n"
            f"🤖 Welcome to Extreme SMS Bot.\n"
            f"👇 নিচের মেনু থেকে অপশন সিলেক্ট করুন:")
            
    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args
    context.user_data.clear() 
    
    conn = get_db()
    c = conn.cursor()
    user_data = c.execute("SELECT * FROM users WHERE user_id=?", (user.id,)).fetchone()
    
    if not user_data:
        referrer_id = None
        if args and args[0].isdigit():
            possible_ref = int(args[0])
            if possible_ref != user.id:
                ref_user = c.execute("SELECT * FROM users WHERE user_id=?", (possible_ref,)).fetchone()
                if ref_user:
                    referrer_id = possible_ref
                    c.execute("UPDATE users SET balance = balance + ?, ref_count = ref_count + 1 WHERE user_id=?", (REFERRAL_REWARD, referrer_id))
                    bonus = check_milestones(referrer_id, ref_user['ref_count'] + 1)
                    try: await context.bot.send_message(referrer_id, f"🎉 **New Referral!**\nUser: {user.first_name}\nReward: +{REFERRAL_REWARD} TK")
                    except: pass

        c.execute("INSERT INTO users (user_id, first_name, username, balance, referrer_id, join_date) VALUES (?, ?, ?, ?, ?, ?)",
                  (user.id, user.first_name, user.username, 10, referrer_id, datetime.now().strftime("%Y-%m-%d")))
        conn.commit()
    
    if user_data and user_data['is_banned']:
        await update.message.reply_text("🚫 **You are BANNED.**")
        conn.close()
        return

    conn.close()
    await show_main_menu(update, context)

# ================== 👤 USER FEATURES ==================

async def balance_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = get_db()
    bal = conn.execute("SELECT balance FROM users WHERE user_id=?", (update.effective_user.id,)).fetchone()[0]
    conn.close()
    await update.message.reply_text(f"💰 **Your Balance:** {bal} TK", parse_mode="Markdown")

async def refer_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    bot_link = f"https://t.me/{BOT_USERNAME}?start={uid}"
    
    conn = get_db()
    u = conn.execute("SELECT ref_count FROM users WHERE user_id=?", (uid,)).fetchone()
    conn.close()
    
    text = (f"👥 **Invite & Earn**\n\nLink: `{bot_link}`\n\n"
            f"📊 Total Invites: {u['ref_count']}\n💰 Per Refer: {REFERRAL_REWARD} TK\n\n"
            f"🎁 **Bonus:** 5 Refs = +20 TK, 10 Refs = +50 TK")
    await update.message.reply_text(text, parse_mode="Markdown")

async def profile_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = get_db()
    u = conn.execute("SELECT * FROM users WHERE user_id=?", (update.effective_user.id,)).fetchone()
    conn.close()
    badge = get_badge(u['ref_count'])
    text = (f"👤 **My Profile**\n\n📛 Name: {u['first_name']}\n🆔 ID: `{u['user_id']}`\n"
            f"💰 Balance: **{u['balance']} TK**\n👥 Referrals: {u['ref_count']}\n🎖 Badge: {badge}\n📅 Joined: {u['join_date']}")
    await update.message.reply_text(text, parse_mode="Markdown")

async def daily_bonus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    today = str(date.today())
    conn = get_db()
    c = conn.cursor()
    user = c.execute("SELECT last_bonus_date, balance FROM users WHERE user_id=?", (user_id,)).fetchone()
    
    if user['last_bonus_date'] == today:
        await update.message.reply_text("❌ **আজকের বোনাস নেওয়া হয়েছে!** আগামীকাল আবার চেষ্টা করুন।", parse_mode="Markdown")
    else:
        c.execute("UPDATE users SET balance = balance + ?, last_bonus_date = ? WHERE user_id=?", (DAILY_BONUS_AMOUNT, today, user_id))
        conn.commit()
        await update.message.reply_text(f"✅ **Daily Bonus Claimed!**\nAdded: +{DAILY_BONUS_AMOUNT} TK\nNew Balance: {user['balance'] + DAILY_BONUS_AMOUNT} TK", parse_mode="Markdown")
    conn.close()

async def leaderboard_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = get_db()
    top = conn.execute("SELECT first_name, ref_count FROM users ORDER BY ref_count DESC LIMIT 10").fetchall()
    conn.close()
    text = "🏆 **Top 10 Referrers**\n\n"
    for i, u in enumerate(top, 1): text += f"{i}. {u['first_name']} - {u['ref_count']} Refs\n"
    await update.message.reply_text(text, parse_mode="Markdown")

async def history_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = get_db()
    logs = conn.execute("SELECT number, message, timestamp FROM sms_history WHERE user_id=? ORDER BY id DESC LIMIT 5", (update.effective_user.id,)).fetchall()
    conn.close()
    text = "📜 **Last 5 SMS History**\n\n" + ("\n".join([f"🕒 {l['timestamp']}\n📱 {l['number']}\n✉️ {l['message']}\n" for l in logs]) if logs else "No history.")
    await update.message.reply_text(text, parse_mode="Markdown")

async def support_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"🆘 **Support:**\nContact Admin: https://t.me/{DEVELOPER_USERNAME.replace('@', '')}")

# ================== 📩 SMS SENDING FLOW ==================
async def start_sms(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_join(update, context): return ConversationHandler.END
    
    conn = get_db()
    user = conn.execute("SELECT balance, is_banned FROM users WHERE user_id=?", (update.effective_user.id,)).fetchone()
    conn.close()
    
    if user['is_banned']:
        await update.message.reply_text("🚫 You are banned.")
        return ConversationHandler.END
    if user['balance'] < MIN_SMS_COST:
        await update.message.reply_text("❌ **Insufficient Balance!**")
        return ConversationHandler.END

    await update.message.reply_text("📱 **Enter Recipient Number:**\n(Example: 01xxxxxxxxx)", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="cancel")]]))
    return PHONE

async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    num = update.message.text.strip()
    if not num.startswith("01") or len(num) != 11 or not num.isdigit():
        await update.message.reply_text("❌ **Invalid Number!** Try again:")
        return PHONE
    context.user_data['to'] = num
    await update.message.reply_text("📝 **Enter Message Body:**")
    return MESSAGE

async def get_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message.text
    context.user_data['msg'] = msg
    text = f"📢 **Confirm SMS?**\n\n📱 To: `{context.user_data['to']}`\n📝 Msg: `{msg}`\n💰 Cost: {MIN_SMS_COST} TK"
    buttons = [[InlineKeyboardButton("✅ Send", callback_data="sms_confirm"), InlineKeyboardButton("❌ Cancel", callback_data="cancel")]]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")
    return CONFIRM

async def send_sms_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    
    if query.data == "cancel":
        await query.edit_message_text("❌ SMS Cancelled.")
        return ConversationHandler.END

    last_time = context.user_data.get('last_sms_time', 0)
    if (datetime.now().timestamp() - last_time) < RATE_LIMIT_SEC:
        await query.edit_message_text(f"⏳ Please wait {RATE_LIMIT_SEC} seconds.")
        return ConversationHandler.END

    conn = get_db()
    c = conn.cursor()
    balance = c.execute("SELECT balance FROM users WHERE user_id=?", (uid,)).fetchone()['balance']
    
    if balance < MIN_SMS_COST:
        conn.close()
        await query.edit_message_text("❌ Insufficient Balance.")
        return ConversationHandler.END

    try:
        await query.edit_message_text("🔄 **Sending SMS...**", parse_mode="Markdown")
        params = {"apiKey": SMS_API_KEY, "senderId": SENDER_ID, "transactionType": "T", "mobileNo": context.user_data['to'], "message": context.user_data['msg']}
        r = requests.get(SMS_API_BASE, params=params, timeout=15)
        
        if r.status_code == 200:
            c.execute("UPDATE users SET balance = balance - ? WHERE user_id=?", (MIN_SMS_COST, uid))
            c.execute("INSERT INTO sms_history (user_id, number, message, status, timestamp) VALUES (?, ?, ?, ?, ?)",
                      (uid, context.user_data['to'], context.user_data['msg'], "Sent", datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            conn.commit()
            context.user_data['last_sms_time'] = datetime.now().timestamp()
            await query.edit_message_text(f"✅ **SMS Sent!**\nRemaining: {balance - MIN_SMS_COST} TK")
        else:
            await query.edit_message_text(f"❌ API Error: {r.text}")
    except Exception as e:
        await query.edit_message_text(f"❌ Error: {str(e)}")
    
    conn.close()
    return ConversationHandler.END

# ================== ⚙️ ADMIN PANEL ==================
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    text = "👮‍♂️ **Admin Dashboard**"
    keyboard = [
        [InlineKeyboardButton("📊 Stats", callback_data="adm_stats"), InlineKeyboardButton("📢 Broadcast", callback_data="adm_broadcast")],
        [InlineKeyboardButton("➕ Add Balance", callback_data="adm_addbal"), InlineKeyboardButton("➖ Deduct/Reset", callback_data="adm_reset")],
        [InlineKeyboardButton("💾 Backup DB", callback_data="adm_backup"), InlineKeyboardButton("🚫 Ban User", callback_data="adm_ban")]
    ]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def admin_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data == "adm_stats":
        conn = get_db()
        users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        sms = conn.execute("SELECT COUNT(*) FROM sms_history").fetchone()[0]
        money = conn.execute("SELECT SUM(balance) FROM users").fetchone()[0]
        conn.close()
        await query.edit_message_text(f"📊 **Stats**\n\n👥 Users: {users}\n📨 SMS: {sms}\n💰 Total Balance: {money} TK", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="adm_back")]]))
    
    elif data == "adm_backup":
        await context.bot.send_document(chat_id=ADMIN_ID, document=open(DB_FILE, 'rb'), caption="🗂 DB Backup")
    
    elif data == "adm_back":
        keyboard = [
            [InlineKeyboardButton("📊 Stats", callback_data="adm_stats"), InlineKeyboardButton("📢 Broadcast", callback_data="adm_broadcast")],
            [InlineKeyboardButton("➕ Add Balance", callback_data="adm_addbal"), InlineKeyboardButton("➖ Deduct/Reset", callback_data="adm_reset")],
            [InlineKeyboardButton("💾 Backup DB", callback_data="adm_backup"), InlineKeyboardButton("🚫 Ban User", callback_data="adm_ban")]
        ]
        await query.edit_message_text("👮‍♂️ **Admin Dashboard**", reply_markup=InlineKeyboardMarkup(keyboard))
        return ConversationHandler.END
        
    elif data in ["adm_addbal", "adm_broadcast", "adm_ban", "adm_reset"]:
        context.user_data['admin_action'] = data
        prompts = {
            "adm_addbal": "💰 **Add Balance**\nSend: `User_ID Amount`",
            "adm_broadcast": "📢 **Broadcast**\nSend message.",
            "adm_ban": "🚫 **Ban User**\nSend: `User_ID`",
            "adm_reset": "🔄 **Reset Balance**\nSend: `User_ID`"
        }
        await query.edit_message_text(prompts[data], parse_mode="Markdown")
        return ADMIN_INPUT

async def admin_process_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return ConversationHandler.END
    action = context.user_data.get('admin_action')
    msg = update.message.text
    conn = get_db()
    c = conn.cursor()
    
    try:
        if action == "adm_addbal":
            uid, amt = map(int, msg.split())
            c.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (amt, uid))
            await update.message.reply_text(f"✅ Added {amt} TK to {uid}")
            try: await context.bot.send_message(uid, f"🎁 **Admin added {amt} TK.**")
            except: pass
        elif action == "adm_ban":
            uid = int(msg)
            c.execute("UPDATE users SET is_banned = 1 WHERE user_id=?", (uid,))
            await update.message.reply_text(f"🚫 User {uid} BANNED.")
        elif action == "adm_broadcast":
            users = c.execute("SELECT user_id FROM users").fetchall()
            await update.message.reply_text(f"🚀 Broadcasting to {len(users)} users...")
            for u in users:
                try: await update.message.copy(chat_id=u['user_id'])
                except: pass
            await update.message.reply_text("✅ Done.")
        elif action == "adm_reset":
            uid = int(msg)
            c.execute("UPDATE users SET balance = 0 WHERE user_id=?", (uid,))
            await update.message.reply_text(f"🔄 Balance reset for {uid}.")
        conn.commit()
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")
    conn.close()
    return ConversationHandler.END

# ================== 🏁 MAIN EXECUTION ==================
if __name__ == "__main__":
    init_db()
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    # SMS Flow
    sms_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^📩 Send SMS$"), start_sms)],
        states={
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)],
            MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_message)],
            CONFIRM: [CallbackQueryHandler(send_sms_confirm)]
        },
        fallbacks=[CommandHandler("start", start)],
    )
    
    # Admin Flow
    admin_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_callback_handler, pattern="^adm_")],
        states={ADMIN_INPUT: [MessageHandler(filters.ALL & ~filters.COMMAND, admin_process_input)]},
        fallbacks=[CallbackQueryHandler(admin_callback_handler, pattern="adm_back")]
    )
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(sms_handler)
    app.add_handler(admin_conv)
    
    # Text Handlers for Button Bar
    app.add_handler(MessageHandler(filters.Regex("^💰 Balance$"), balance_handler))
    app.add_handler(MessageHandler(filters.Regex("^👤 My Profile$"), profile_handler))
    app.add_handler(MessageHandler(filters.Regex("^👥 Invite Friends$"), refer_handler))
    app.add_handler(MessageHandler(filters.Regex("^🎁 Daily Bonus$"), daily_bonus))
    app.add_handler(MessageHandler(filters.Regex("^🏆 Leaderboard$"), leaderboard_handler))
    app.add_handler(MessageHandler(filters.Regex("^📜 History$"), history_handler))
    app.add_handler(MessageHandler(filters.Regex("^🆘 Support$"), support_handler))
    app.add_handler(MessageHandler(filters.Regex("^⚙️ Admin Panel$"), admin_panel))
    
    print("✅ Bot Started with BUTTON BAR...")
    app.run_polling()
