import logging
import sqlite3
import requests
import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ConversationHandler
)

# ================== CONFIGURATION ==================
TELEGRAM_TOKEN = "8345293297:AAHv6KfWaFsXJ-rlbJwupBqgTHbKt3CWS5U"
ADMIN_ID = 7008757477
CHANNEL_USERNAME = "@ExtremeLevelTech" 

# SMS API CONFIG
SMS_API_BASE = "http://sms.greenheritageit.com/smsapi"
SMS_API_KEY = "$2y$10$8cKMTQTz6E0hdmbghuOjS.NLPWxolWv99uTlHoLC5VCXWq//Wk1D277"
SENDER_ID = "MultiSports"

# DATABASE & STATES
DB_FILE = "bot_database.db"
PHONE, MESSAGE, CONFIRM = range(3)

# ================== LOGGING ==================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ================== DATABASE MANAGEMENT ==================
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Users Table
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        first_name TEXT,
        balance INTEGER DEFAULT 10,
        ref_count INTEGER DEFAULT 0,
        referrer_id INTEGER,
        join_date TEXT
    )''')
    
    # SMS History
    c.execute('''CREATE TABLE IF NOT EXISTS sms_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        number TEXT,
        message TEXT,
        timestamp TEXT
    )''')
    
    # Milestone Claims
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

# ================== HELPER FUNCTIONS ==================
async def check_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    try:
        member = await context.bot.get_chat_member(CHANNEL_USERNAME, user_id)
        if member.status in ["member", "administrator", "creator"]:
            return True
    except:
        return True 
    
    keyboard = [
        [InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}")],
        [InlineKeyboardButton("✅ Verified", callback_data="main_menu")]
    ]
    await context.bot.send_message(
        chat_id=user_id,
        text="⚠️ বট ব্যবহার করতে হলে আমাদের চ্যানেলে জয়েন করুন।",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return False

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

# ================== MAIN MENU & START ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args
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
                    c.execute("UPDATE users SET balance = balance + 5, ref_count = ref_count + 1 WHERE user_id=?", (referrer_id,))
                    new_ref_count = ref_user['ref_count'] + 1
                    bonus = check_milestones(referrer_id, new_ref_count)
                    try:
                        await context.bot.send_message(chat_id=referrer_id, text=f"🎉 নতুন রেফারেল! (+5 টাকা){' + বোনাস' if bonus else ''}")
                    except: pass

        c.execute("INSERT INTO users (user_id, first_name, balance, referrer_id, join_date) VALUES (?, ?, ?, ?, ?)",
                  (user.id, user.first_name, 10, referrer_id, datetime.now().strftime("%Y-%m-%d")))
        conn.commit()
    conn.close()
    await show_main_menu(update, context)

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, text=None):
    user_id = update.effective_user.id
    if text is None:
        text = f"👋 হ্যালো {update.effective_user.first_name}!\n🤖 **Extreme SMS Bot** এ স্বাগতম।"

    # User Buttons
    keyboard = [
        [InlineKeyboardButton("📩 Send SMS", callback_data="sms_start"), InlineKeyboardButton("💰 Balance", callback_data="balance")],
        [InlineKeyboardButton("👥 Refer & Earn", callback_data="refer"), InlineKeyboardButton("🏆 Leaderboard", callback_data="top_list")],
        [InlineKeyboardButton("📜 History", callback_data="history"), InlineKeyboardButton("🆘 Support", url="https://t.me/ExtremeLevelTech")]
    ]

    # ADMIN PANEL BUTTON (Only for Admin)
    if user_id == ADMIN_ID:
        keyboard.append([InlineKeyboardButton("⚙️ Admin Panel", callback_data="admin_panel")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.message:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")

# ================== USER FEATURES ==================
async def balance_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    conn = get_db()
    user = conn.execute("SELECT balance, ref_count FROM users WHERE user_id=?", (query.from_user.id,)).fetchone()
    conn.close()
    text = f"💰 **ব্যালেন্স ইনফো**\n\n💸 বর্তমান ব্যালেন্স: {user['balance']} টাকা\n👥 মোট রেফার: {user['ref_count']} জন"
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]), parse_mode="Markdown")

async def refer_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    bot_link = f"https://t.me/{context.bot.username}?start={uid}"
    conn = get_db()
    ref_count = conn.execute("SELECT ref_count FROM users WHERE user_id=?", (uid,)).fetchone()['ref_count']
    conn.close()
    text = f"👥 **Refer & Earn**\n\n🔗 লিংক:\n`{bot_link}`\n\n📊 রেফার করেছেন: {ref_count} জন\n💰 প্রতি রেফারে: 5 টাকা"
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]), parse_mode="Markdown")

async def leaderboard_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    conn = get_db()
    top_users = conn.execute("SELECT first_name, ref_count FROM users ORDER BY ref_count DESC LIMIT 10").fetchall()
    conn.close()
    text = "🏆 **Top 10 Leaders**\n\n" + "\n".join([f"{i+1}. {u['first_name']} - {u['ref_count']} Refs" for i, u in enumerate(top_users)])
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]), parse_mode="Markdown")

async def history_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    conn = get_db()
    logs = conn.execute("SELECT number, message, timestamp FROM sms_history WHERE user_id=? ORDER BY id DESC LIMIT 5", (query.from_user.id,)).fetchall()
    conn.close()
    text = "📜 **SMS History**\n\n" + ("\n".join([f"🕒 {l['timestamp']}\n📱 {l['number']}\n✉️ {l['message']}\n" for l in logs]) if logs else "No history.")
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]), parse_mode="Markdown")

# ================== ADMIN PANEL FEATURES ==================
async def admin_panel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != ADMIN_ID:
        return

    text = "⚙️ **Admin Control Panel**\n\nকি করতে চান সিলেক্ট করুন:"
    keyboard = [
        [InlineKeyboardButton("📊 Bot Statistics", callback_data="adm_stats")],
        [InlineKeyboardButton("📢 How to Broadcast?", callback_data="adm_bc_info")],
        [InlineKeyboardButton("💰 How to Add Balance?", callback_data="adm_bal_info")],
        [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != ADMIN_ID: return

    conn = get_db()
    total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    total_sms = conn.execute("SELECT COUNT(*) FROM sms_history").fetchone()[0]
    total_bal = conn.execute("SELECT SUM(balance) FROM users").fetchone()[0]
    conn.close()

    text = (
        f"📊 **Bot Live Statistics**\n\n"
        f"👥 Total Users: {total_users}\n"
        f"📨 Total SMS Sent: {total_sms}\n"
        f"💰 User Holdings: {total_bal} BDT"
    )
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Admin Panel", callback_data="admin_panel")]]), parse_mode="Markdown")

async def admin_info_pages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    
    if data == "adm_bc_info":
        text = "📢 **Broadcast করার নিয়ম:**\n\nকমান্ড টাইপ করুন:\n`/broadcast আপনার মেসেজ`\n\nউদাহরণ:\n`/broadcast আগামীকাল সার্ভার মেইনটেইন্যান্স হবে।`"
    elif data == "adm_bal_info":
        text = "💰 **ব্যালেন্স এড করার নিয়ম:**\n\nকমান্ড টাইপ করুন:\n`/addbal User_ID Amount`\n\nউদাহরণ:\n`/addbal 12345678 100`"
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Admin Panel", callback_data="admin_panel")]]), parse_mode="Markdown")

# ================== ADMIN COMMANDS ==================
async def add_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    try:
        uid, amt = int(context.args[0]), int(context.args[1])
        conn = get_db()
        conn.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (amt, uid))
        conn.commit()
        conn.close()
        await update.message.reply_text(f"✅ {amt} added to {uid}")
        try: await context.bot.send_message(uid, f"🎁 Admin added {amt} balance.")
        except: pass
    except: await update.message.reply_text("Usage: /addbal <uid> <amount>")

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    msg = " ".join(context.args)
    if not msg:
        await update.message.reply_text("Usage: /broadcast <message>")
        return

    conn = get_db()
    users = conn.execute("SELECT user_id FROM users").fetchall()
    conn.close()
    
    await update.message.reply_text(f"🚀 Broadcasting to {len(users)} users...")
    count = 0
    for u in users:
        try:
            await context.bot.send_message(u['user_id'], msg)
            count += 1
            await asyncio.sleep(0.05)
        except: pass
    await update.message.reply_text(f"✅ Sent to {count} users.")

# ================== SMS CONVERSATION ==================
async def start_sms(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not await check_join(update, context): return ConversationHandler.END
    
    conn = get_db()
    bal = conn.execute("SELECT balance FROM users WHERE user_id=?", (query.from_user.id,)).fetchone()['balance']
    conn.close()
    
    if bal < 1:
        await query.answer("❌ ব্যালেন্স নেই!", show_alert=True)
        return ConversationHandler.END
        
    await query.edit_message_text("📱 **নাম্বার দিন (01xxxxxxxxx):**", parse_mode="Markdown")
    return PHONE

async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    num = update.message.text
    if len(num) != 11 or not num.startswith("01") or not num.isdigit():
        await update.message.reply_text("❌ ভুল নাম্বার। আবার দিন।")
        return PHONE
    context.user_data['to'] = num
    await update.message.reply_text("✉️ **মেসেজ লিখুন:**")
    return MESSAGE

async def get_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['msg'] = update.message.text
    text = f"📱 To: `{context.user_data['to']}`\n✉️ Msg: {context.user_data['msg']}\n💰 Cost: 1 TK"
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ Send", callback_data="do_send"), InlineKeyboardButton("❌ Cancel", callback_data="main_menu")]]), parse_mode="Markdown")
    return CONFIRM

async def send_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    
    conn = get_db()
    if conn.execute("SELECT balance FROM users WHERE user_id=?", (uid,)).fetchone()['balance'] < 1:
        conn.close(); await query.edit_message_text("❌ ব্যালেন্স শেষ।"); return ConversationHandler.END
    
    try:
        await query.edit_message_text("🔄 Sending...")
        params = {"apiKey": SMS_API_KEY, "senderId": SENDER_ID, "transactionType": "T", "mobileNo": context.user_data['to'], "message": context.user_data['msg']}
        requests.get(SMS_API_BASE, params=params, timeout=10)
        
        conn.execute("UPDATE users SET balance = balance - 1 WHERE user_id=?", (uid,))
        conn.execute("INSERT INTO sms_history (user_id, number, message, timestamp) VALUES (?, ?, ?, ?)", (uid, context.user_data['to'], context.user_data['msg'], datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        await query.edit_message_text("✅ SMS Sent!")
    except Exception as e:
        await query.edit_message_text(f"❌ Failed: {e}")
    
    conn.close()
    return ConversationHandler.END

# ================== RUN BOT ==================
if __name__ == "__main__":
    init_db()
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("addbal", add_balance))
    app.add_handler(CommandHandler("broadcast", broadcast))
    
    sms_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_sms, pattern="sms_start")],
        states={PHONE: [MessageHandler(filters.TEXT, get_phone)], MESSAGE: [MessageHandler(filters.TEXT, get_message)], CONFIRM: [CallbackQueryHandler(send_confirm, pattern="do_send")]},
        fallbacks=[CallbackQueryHandler(show_main_menu, pattern="main_menu")]
    )
    app.add_handler(sms_conv)
    
    app.add_handler(CallbackQueryHandler(balance_handler, pattern="balance"))
    app.add_handler(CallbackQueryHandler(refer_handler, pattern="refer"))
    app.add_handler(CallbackQueryHandler(leaderboard_handler, pattern="top_list"))
    app.add_handler(CallbackQueryHandler(history_handler, pattern="history"))
    app.add_handler(CallbackQueryHandler(show_main_menu, pattern="main_menu"))
    
    # Admin Panel Handlers
    app.add_handler(CallbackQueryHandler(admin_panel_handler, pattern="admin_panel"))
    app.add_handler(CallbackQueryHandler(admin_stats, pattern="adm_stats"))
    app.add_handler(CallbackQueryHandler(admin_info_pages, pattern="^(adm_bc_info|adm_bal_info)$"))

    print("✅ Bot Started with Admin Panel Fixed...")
    app.run_polling()
