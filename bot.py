# ১. লাইব্রেরি ইনস্টল
!pip install python-telegram-bot requests nest_asyncio

import logging
import requests
import nest_asyncio
import asyncio
import json
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler

# =================CONFIGURATIONS=================
TELEGRAM_TOKEN = '8345293297:AAE6yn3WPN-3Wobg68EVUo4rMMxSAhBaLkk'
SMS_API_URL = "http://sms.greenheritageit.com/smsapi"

# আপনার API Key
SMS_API_KEY = "$2y$10$8cKMTQTz6E0hdmbghuOjS.NLPWxolWv99uTlHoLC5VCXWq//Wk1D277"

# Mask Name
MASK_NAME = "MultiSports"
# ================================================

nest_asyncio.apply()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="বট রেডি! ✅\nSMS পাঠাতে লিখুন:\n`/sms 019XXXXXXXX Hello World`",
        parse_mode='Markdown'
    )

async def send_sms_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    args = context.args

    # ফরম্যাট চেক
    if len(args) < 2:
        await context.bot.send_message(chat_id=chat_id, text="⚠️ ভুল ফরম্যাট! লিখুন: `/sms নম্বর মেসেজ`", parse_mode='Markdown')
        return

    mobile_no = args[0]
    # মেসেজের সব শব্দ জোড়া লাগানো হচ্ছে (স্পেসসহ)
    message_body = ' '.join(args[1:])

    status_msg = await context.bot.send_message(chat_id=chat_id, text="🔄 সার্ভারে রিকোয়েস্ট পাঠানো হচ্ছে...")

    try:
        # Payload তৈরি
        payload = {
            "api_key": SMS_API_KEY,
            "transaction_type": "T",
            "campaign_id": "",
            "sms_data": [
                {
                    "recipient": mobile_no,
                    "sender_id": MASK_NAME,
                    "message": message_body
                }
            ]
        }

        # 🔥 স্পেশাল ফিক্স: Compact JSON তৈরি করা
        # separators=(',', ':') ব্যবহার করায় JSON এর স্ট্রাকচারে কোনো বাড়তি স্পেস থাকবে না।
        # এটি সার্ভারকে কনফিউজড হওয়া থেকে বাঁচাবে।
        json_payload = json.dumps(payload, separators=(',', ':'))

        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

        loop = asyncio.get_running_loop()

        # data=json_payload ব্যবহার করা হচ্ছে (json=payload নয়)
        response = await loop.run_in_executor(
            None,
            lambda: requests.post(SMS_API_URL, data=json_payload, headers=headers)
        )

        # রেসপন্স হ্যান্ডলিং
        response_text = response.text
        try:
            response_data = response.json()
            api_status = str(response_data.get('status', '')).lower()
            api_msg = response_data.get('message', '')

            # সফল হলে
            if response.status_code == 200 and api_status == 'success':
                 await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=status_msg.message_id,
                    text=f"✅ সফল হয়েছে! (Success)\n\n"
                         f"📱 নম্বর: {mobile_no}\n"
                         f"✉️ মেসেজ: {message_body}\n"
                         f"🔍 সার্ভার মেসেজ: {api_msg}"
                )
            else:
                # ফেইল হলে
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=status_msg.message_id,
                    text=f"❌ ফেইলড! (Failed)\nStatus: {api_status}\nMessage: {api_msg}\nServer Raw: {response_text}"
                )
        except:
             await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=status_msg.message_id,
                text=f"❌ রেসপন্স এরর:\n{response_text}"
            )

    except Exception as e:
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=status_msg.message_id,
            text=f"❌ সিস্টেম এরর: {str(e)}"
        )

async def main():
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('sms', send_sms_command))

    print("🤖 Bot is running...")
    await application.run_polling()

if __name__ == '__main__':
    try:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main())
    except RuntimeError:
        loop = asyncio.get_event_loop()
        loop.create_task(main())
