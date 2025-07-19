import os
import json
import logging
import datetime
import requests
from telegram import (
    Update,
    ChatMember,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
    CallbackQueryHandler,
)

# ----------------------------
# تنظیمات اولیه و لاگینگ
# ----------------------------
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# ----------------------------
# کانفیگ API و متغیرها
# ----------------------------
TELEGRAM_TOKEN = "7784966158:AAEydBAaUlF99f3o9_-oN-84-WUrhjEg_MM"
LLM_API_KEY = "app-AL4fTkUVtLptvaTgC1v6qrZl"
BASE_URL = "https://difysrv.yarai.ir/v1"
CHAT_URL = f"{BASE_URL}/chat-messages"
UPLOAD_URL = f"{BASE_URL}/files/upload"
AUDIO_TO_TEXT_URL = f"{BASE_URL}/audio-to-text"


# لینک‌های پرداخت
PAY_LINK_50 = "https://zarinp.al/708600"
PAY_LINK_100 = "https://zarinp.al/708601"
VISIT_PAY_LINK = "https://zarinp.al/713497"

# محدودیت پیام رایگان هفتگی
FREE_MESSAGES_PER_WEEK = 1000

# کانال تلگرام برای الزام عضویت
CHANNEL_USERNAME = "@medhoush_ir"

# آیدی‌های ادمین
ADMIN_IDS = [6234375011,105795770]

# آیدی‌های پزشکان
DOCTOR_IDS = [83900221]  # لیست آی‌دی‌های عددی پزشکان

# مسیر فایل داده‌های پرداخت
PAYMENT_FILE = "payment_requests.json"
VISIT_PAYMENT_FILE = "visit_payment_requests.json"

# نگاشت مکالمات فعال
ACTIVE_CONVERSATIONS = {}  # {user_id: doctor_id}

# کیبورد اصلی
MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("🗨️ گفتگو با مدهوش")],
        [KeyboardButton("💳 خرید بسته"), KeyboardButton("📊 نمایش اعتبار فعلی")],
        [KeyboardButton("ℹ️ درباره ما"), KeyboardButton("📄 ویزیت و نسخه پزشک")],
    ],
    resize_keyboard=True,
)

# کیبورد ادمین
ADMIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("📋 درخواست‌های پرداخت")],
        [KeyboardButton("🔍 وضعیت کاربر"), KeyboardButton("🌐 گزارش کلی")],
        [KeyboardButton("🔙 برگشت به منوی عادی")],
    ],
    resize_keyboard=True,
)

# کیبورد ویزیت
VISIT_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("💬 گفتگو با پزشک")],
        [KeyboardButton("اتمام گفتگو")],
        [KeyboardButton("🔙 بازگشت به منوی اصلی")],
    ],
    resize_keyboard=True,
)

# ----------------------------
# کمک‌های تابعی
# ----------------------------
def remove_markdown(text: str) -> str:
    return text.replace("*", "").replace("_", "").replace("`", "")

def is_admin(user_id: int) -> bool:
    print(f"----------------- this is uder_id {user_id}")
    """بررسی اینکه آیا کاربر ادمین است یا خیر"""
    return user_id in ADMIN_IDS

def load_requests(file_path: str):
    """بارگیری درخواست‌ها از فایل"""
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"Error loading requests from {file_path}: {e}")
            return []
    return []

def save_requests(file_path: str, requests):
    """ذخیره درخواست‌ها در فایل"""
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(requests, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"Error saving requests to {file_path}: {e}")

async def is_user_member_of_channel(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """بررسی عضویت کاربر در کانال"""
    try:
        # member = await context.bot.get_chat_member(CHANNEL_USERNAME, user_id)
        # return member.status in (
        #     ChatMember.MEMBER,
        #     ChatMember.ADMINISTRATOR,
        #     ChatMember.OWNER,
        # )
        return True
    except Exception as e:
        logging.error(f"Error checking channel membership: {e}")
        return False

async def transcribe_audio(audio_path):
    """تبدیل فایل صوتی به متن"""
    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}"
    }
    try:
        with open(audio_path, 'rb') as audio_file:
            files = {'file': (os.path.basename(audio_path), audio_file, 'audio/ogg')}
            response = requests.post(AUDIO_TO_TEXT_URL, headers=headers, files=files)
            if response.status_code == 200:
                return response.json().get('text', '')
            else:
                logging.error(f"Transcription failed: {response.status_code}, {response.text}")
                return None
    except Exception as e:
        logging.error(f"Audio transcription error: {e}")
        return None

async def upload_file(file_path, user_id, file_type):
    """Upload file to the API and return the file ID"""
    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}"
    }
    mime_types = {
        'image': {
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.webp': 'image/webp',
            '.gif': 'image/gif'
        },
        'document': {
            '.pdf': 'application/pdf',
            '.txt': 'text/plain',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        }
    }
    ext = os.path.splitext(file_path)[1].lower()
    mime_type = mime_types[file_type].get(ext, 'application/octet-stream')
    try:
        with open(file_path, 'rb') as file:
            files = {
                'file': (os.path.basename(file_path), file, mime_type)
            }
            data = {
                'user': str(user_id)
            }
            logging.info("Uploading file to the server.")
            response = requests.post(UPLOAD_URL, headers=headers, files=files, data=data)
            if response.status_code in [200, 201]:
                logging.info(f"File uploaded successfully. Response: {response.text}")
                return response.json().get('id')
            else:
                logging.error(f"Upload failed with status {response.status_code}: {response.text}")
                return None
    except Exception as e:
        logging.error(f"File upload error: {e}")
        return None

async def call_llm_api(user_id, query, conversation_id=None, upload_file_id=None, file_type=None):
    """Call the chat API with the given parameters"""
    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "inputs": {},
        "query": query,
        "response_mode": "blocking",
        "conversation_id": conversation_id,
        "user": str(user_id),
        "files": []
    }
    if upload_file_id and file_type:
        data["files"].append({
            "type": file_type,
            "transfer_method": "local_file",
            "upload_file_id": upload_file_id
        })
    try:
        logging.info("Sending request to LLM API.")
        response = requests.post(CHAT_URL, json=data, headers=headers)
        if response.status_code == 200:
            logging.info("Received successful response from LLM API.")
            response_json = response.json()
            return {
                "response": response_json.get("answer", "No answer received."),
                "message_id": response_json.get("message_id"),
                "conversation_id": response_json.get("conversation_id", conversation_id)
            }
        else:
            logging.error(f"API Error (Status {response.status_code}): {response.text}")
            return {"response": "Sorry, there was an error processing your request. Please try again later."}
    except Exception as e:
        logging.error(f"API request error: {e}")
        return {"response": "Sorry, there was an error processing your request."}

async def check_credit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """بررسی اعتبار کاربر و پیام‌های رایگان"""
    user_data = context.user_data
    today = update.message.date.date()
    current_week_start = today - datetime.timedelta(days=today.weekday())
    if "week_start" not in user_data or user_data["week_start"] != current_week_start:
        user_data["week_start"] = current_week_start
        user_data["credit"] = FREE_MESSAGES_PER_WEEK
    if user_data.get("credit", 0) <= 0:
        await update.message.reply_text(
            "⚠️ اعتبار هفتگی شما به پایان رسیده است. برای ادامه لطفا بسته خریداری کنید.",
            reply_markup=MAIN_KEYBOARD
        )
        return False
    user_data["credit"] -= 1
    return True

def add_payment_request(user_id, username, package_type, amount, receipt_id, file_path: str):
    """اضافه کردن درخواست پرداخت به لیست درخواست‌ها"""
    requests = load_requests(file_path)
    new_request = {
        "id": len(requests) + 1,
        "user_id": user_id,
        "username": username,
        "package_type": package_type,
        "amount": amount,
        "receipt_id": receipt_id,
        "status": "pending",
        "timestamp": datetime.datetime.now().isoformat(),
        "processed_by": None,
        "processed_at": None
    }
    requests.append(new_request)
    save_requests(file_path, requests)
    return new_request["id"]

def update_payment_status(request_id, status, admin_id, file_path: str):
    """بروزرسانی وضعیت درخواست پرداخت"""
    requests = load_requests(file_path)
    for req in requests:
        if req["id"] == request_id:
            req["status"] = status
            req["processed_by"] = admin_id
            req["processed_at"] = datetime.datetime.now().isoformat()
            save_requests(file_path, requests)
            return True
    return False

# ----------------------------
# هندلرها
# ----------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    logging.info(f"User {user_id} started the bot hello.")
    if not await is_user_member_of_channel(user_id, context):
        await update.message.reply_text(
            "⚠️ لطفا ابتدا در کانال ما عضو شوید تا بتوانید از ربات استفاده کنید:\n"
            "https://t.me/medhoush_ir\n\n"
            "سپس /start را ارسال کنید.",
            reply_markup=MAIN_KEYBOARD
        )
        return
    if is_admin(user_id):
        await update.message.reply_text(
            "🔑 سلام ادمین محترم!\n"
            "به پنل مدیریت مدهوش خوش آمدید. چه کاری می‌توانم برایتان انجام دهم؟",
            reply_markup=ADMIN_KEYBOARD
        )
        return
    if "conversation_id" in context.user_data:
        del context.user_data["conversation_id"]
    welcome = (
        "سلام!\n"
        "خوش اومدید به ⚕️مدهوش⚕️، دستیار پزشکی و سلامت شما.\n\n"
        "✅ هر هفته تا ۷ پیام رایگان دارید.\n"
        "✅ می‌تونید متن، عکس، فایل پزشکی و حتی صدا ارسال کنید.\n"
        "✅ پاسخ دقیق، سریع و قابل اعتماد دریافت کنید.\n\n"
        "برای شروع روی دکمه «🗨️ گفتگو با مدهوش» بزنید."
    )
    await update.message.reply_text(welcome, reply_markup=MAIN_KEYBOARD)

async def about_us(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🤖 مدهوش چیست؟\n"
        "مدهوش یک دستیار پزشکی مبتنی بر هوش مصنوعی است که "
        "با تکیه بر بانک اطلاعاتی معتبر پزشکی، به شما در "
        "درک بیماری‌ها، داروها، رژیم غذایی و تحلیل نتایج آزمایش‌ها کمک می‌کند.\n\n"
        "🔒 امنیت و محرمانگی اطلاعات شما برای ما بسیار مهم است.\n"
        "📡 برای استفاده کامل، لطفاً در کانال رسمی ما عضو شوید:\n"
        "https://t.me/medhoush_ir"
    )
    await update.message.reply_text(text, reply_markup=MAIN_KEYBOARD)

async def show_credit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data = context.user_data
    credit = user_data.get("credit", FREE_MESSAGES_PER_WEEK)
    await update.message.reply_text(
        f"📊 اعتبار باقی‌مانده شما این هفته: {credit} پیام",
        reply_markup=MAIN_KEYBOARD
    )

async def buy_package(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش لینک‌های پرداخت به کاربر"""
    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(text="بسته ۵۰ تایی — ۵۰,۰۰۰ تومان", url=PAY_LINK_50)],
            [InlineKeyboardButton(text="بسته ۱۰۰ تایی — ۸۰,۰۰۰ تومان", url=PAY_LINK_100)],
            [InlineKeyboardButton(text="🧾 ثبت رسید پرداخت", callback_data="submit_receipt")]
        ]
    )
    await update.message.reply_text(
        "💳 لطفاً بسته مورد نظر را انتخاب و پرداخت را تکمیل کنید.\n\n"
        "پس از پرداخت، روی دکمه «🧾 ثبت رسید پرداخت» کلیک کنید و شناسه پرداخت خود را ارسال نمایید.\n"
        "درخواست شما پس از بررسی توسط ادمین تایید خواهد شد.",
        reply_markup=keyboard,
    )

async def submit_receipt_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """هندلر دریافت اطلاعات رسید پرداخت"""
    query = update.callback_query
    await query.answer()

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("بسته ۵۰ تایی (۵۰,۰۰۰ تومان)", callback_data="package_50")],
        [InlineKeyboardButton("بسته ۱۰۰ تایی (۸۰,۰۰۰ تومان)", callback_data="package_100")],
        [InlineKeyboardButton("❌ لغو", callback_data="cancel_receipt")]
    ])

    await query.edit_message_text(
        "لطفا نوع بسته‌ای که خریداری کرده‌اید را انتخاب کنید:",
        reply_markup=keyboard
    )

async def package_selection_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """هندلر انتخاب نوع بسته"""
    query = update.callback_query
    await query.answer()

    choice = query.data

    if choice == "cancel_receipt":
        await query.edit_message_text("درخواست لغو شد.")
        return

    if choice == "package_50":
        context.user_data["package_type"] = "50"
        context.user_data["package_amount"] = 50000
    elif choice == "package_100":
        context.user_data["package_type"] = "100"
        context.user_data["package_amount"] = 80000

    # مرحله دوم: درخواست شناسه پرداخت
    await query.edit_message_text(
        "لطفا شناسه پرداخت یا کد پیگیری خود را وارد کنید:\n\n"
        "این کد معمولاً پس از پرداخت موفق در صفحه درگاه پرداخت یا پیامک بانک به شما نمایش داده می‌شود."
    )

    context.user_data["waiting_for_receipt"] = True

async def receive_receipt_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت شناسه پرداخت از کاربر"""
    if context.user_data.get("waiting_for_receipt"):
        receipt_id = update.message.text
        user_id = update.message.from_user.id
        username = update.message.from_user.username or "بدون نام‌کاربری"
        package_type = context.user_data.get("package_type")
        amount = context.user_data.get("package_amount")

        request_id = add_payment_request(user_id, username, package_type, amount, receipt_id, PAYMENT_FILE)

        del context.user_data["waiting_for_receipt"]
        del context.user_data["package_type"]
        del context.user_data["package_amount"]

        await update.message.reply_text(
            f"✅ درخواست پرداخت شما با شماره پیگیری #{request_id} ثبت شد.\n\n"
            "پس از بررسی و تایید توسط ادمین، اعتبار شما افزایش خواهد یافت.\n"
            "این فرایند معمولاً در کمتر از ۲۴ ساعت انجام می‌شود.",
            reply_markup=MAIN_KEYBOARD
        )

        for admin_id in ADMIN_IDS:
            try:
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ تایید", callback_data=f"approve_{request_id}")],
                    [InlineKeyboardButton("❌ رد", callback_data=f"reject_{request_id}")]
                ])

                await context.bot.send_message(
                    chat_id=admin_id,
                    text=f"🔔 درخواست پرداخت جدید:\n\n"
                    f"شناسه درخواست: #{request_id}\n"
                    f"کاربر: {username} (ID: {user_id})\n"
                    f"بسته: {package_type} تایی\n"
                    f"مبلغ: {amount:,} تومان\n"
                    f"شناسه پرداخت: {receipt_id}\n"
                    f"زمان: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                    "لطفا این درخواست را بررسی و تایید یا رد کنید.",
                    reply_markup=keyboard
                )
            except Exception as e:
                logging.error(f"Error notifying admin {admin_id}: {e}")

        return True
    return False

async def payment_action_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """هندلر تایید یا رد درخواست پرداخت توسط ادمین"""
    query = update.callback_query
    admin_id = query.from_user.id

    if not is_admin(admin_id):
        await query.answer("شما مجوز انجام این عملیات را ندارید.")
        return

    await query.answer()

    if (query.data.startswith("approve1_") or query.data.startswith("reject1_")) and "visit" not in query.data:
        prefix, request_id_str = query.data.split("_", 1)
        request_id = int(request_id_str)

        requests = load_requests(PAYMENT_FILE)
        request = None

        for req in requests:
            if req["id"] == request_id:
                request = req
                break

        if not request:
            await query.edit_message_text("❌ درخواست مورد نظر یافت نشد.")
            return

        user_id = request["user_id"]
        package_type = request["package_type"]

        if prefix == "approve1":
            update_payment_status(request_id, "approved", admin_id, PAYMENT_FILE)
            added_credit = 50 if package_type == "50" else 100
            try:
                user_data = dict(context.application.user_data)

                if user_id not in user_data:
                    user_data[user_id] = {}

                current_credit = user_data[user_id].get("credit", FREE_MESSAGES_PER_WEEK)
                user_data[user_id]["credit"] = current_credit + added_credit

                context.application._user_data = user_data

                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"✅ درخواست پرداخت شما با شناسه #{request_id} تایید شد!\n\n"
                    f"تعداد {added_credit} پیام به اعتبار شما افزوده شد.\n"
                    "با تشکر از خرید شما 🙏",
                    reply_markup=MAIN_KEYBOARD
                )

                await query.edit_message_text(
                    f"✅ درخواست #{request_id} با موفقیت تایید شد.\n"
                    f"تعداد {added_credit} پیام به اعتبار کاربر افزوده شد."
                )
            except Exception as e:
                logging.error(f"Error approving payment: {e}")
                await query.edit_message_text(
                    f"❌ خطا در تایید درخواست #{request_id}:\n{str(e)}"
                )

        elif prefix == "reject1":
            update_payment_status(request_id, "rejected", admin_id, PAYMENT_FILE)

            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"❌ متاسفانه درخواست پرداخت شما با شناسه #{request_id} تایید نشد.\n\n"
                    "لطفا برای بررسی با پشتیبانی تماس بگیرید یا مجددا تلاش کنید.",
                    reply_markup=MAIN_KEYBOARD
                )

                await query.edit_message_text(
                    f"❌ درخواست #{request_id} رد شد."
                )
            except Exception as e:
                logging.error(f"Error rejecting payment: {e}")
                await query.edit_message_text(
                    f"❌ خطا در رد درخواست #{request_id}:\n{str(e)}"
                )

async def admin_view_payments(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش درخواست‌های پرداخت برای ادمین"""
    user_id = update.message.from_user.id

    if not is_admin(user_id):
        await update.message.reply_text("شما مجوز دسترسی به این بخش را ندارید.")
        return

    payment_requests = load_requests(PAYMENT_FILE)

    if not payment_requests:
        await update.message.reply_text(
            "❌ هیچ درخواست پرداختی ثبت نشده است.",
            reply_markup=ADMIN_KEYBOARD
        )
        return

    pending_requests = [req for req in payment_requests if req["status"] == "pending"]

    if not pending_requests:
        await update.message.reply_text(
            "✅ همه درخواست‌های پرداخت پردازش شده‌اند.",
            reply_markup=ADMIN_KEYBOARD
        )

        processed_requests = [req for req in payment_requests if req["status"] != "pending"]
        if processed_requests:
            history_text = "📋 تاریخچه درخواست‌های پردازش شده:\n\n"
            for req in processed_requests[:10]:
                status_emoji = "✅" if req["status"] == "approved" else "❌"
                history_text += f"{status_emoji} #{req['id']} | کاربر: {req['username']} | بسته: {req['package_type']} | تاریخ: {req['processed_at'][:10]}\n"

            await update.message.reply_text(history_text, reply_markup=ADMIN_KEYBOARD)

        return

    text = f"🔔 {len(pending_requests)} درخواست پرداخت در انتظار بررسی:\n\n"

    for req in pending_requests:
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ تایید", callback_data=f"approve_{req['id']}"),
                InlineKeyboardButton("❌ رد", callback_data=f"reject_{req['id']}")
            ]
        ])

        req_text = (
            f"شناسه: #{req['id']}\n"
            f"کاربر: {req['username']} (ID: {req['user_id']})\n"
            f"بسته: {req['package_type']} تایی\n"
            f"مبلغ: {req['amount']:,} تومان\n"
            f"شناسه پرداخت: {req['receipt_id']}\n"
            f"تاریخ: {req['timestamp'][:10]}\n"
        )

        await update.message.reply_text(req_text, reply_markup=keyboard)

async def admin_check_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بررسی وضعیت کاربر خاص توسط ادمین"""
    user_id = update.message.from_user.id

    if not is_admin(user_id):
        await update.message.reply_text("شما مجوز دسترسی به این بخش را ندارید.")
        return

    await update.message.reply_text(
        "لطفا آیدی عددی کاربر مورد نظر را وارد کنید:",
        reply_markup=ADMIN_KEYBOARD
    )

    context.user_data["waiting_for_user_id"] = True

async def receive_user_id_for_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت آیدی کاربر از ادمین برای بررسی"""
    if context.user_data.get("waiting_for_user_id"):
        try:
            target_user_id = int(update.message.text)
            del context.user_data["waiting_for_user_id"]

            user_data = context.application.user_data.get(target_user_id, {})

            payment_requests = load_requests(PAYMENT_FILE)
            user_payments = [req for req in payment_requests if req["user_id"] == target_user_id]

            credit = user_data.get("credit", FREE_MESSAGES_PER_WEEK)

            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ افزایش 10 پیام", callback_data=f"add_credit_{target_user_id}_10")],
                [InlineKeyboardButton("➕ افزایش 50 پیام", callback_data=f"add_credit_{target_user_id}_50")],
                [InlineKeyboardButton("➕ افزایش 100 پیام", callback_data=f"add_credit_{target_user_id}_100")]
            ])

            text = f"📊 اطلاعات کاربر با آیدی {target_user_id}:\n\n"
            text += f"اعتبار فعلی: {credit} پیام\n\n"

            if user_payments:
                text += "💳 سوابق پرداخت:\n"
                for payment in user_payments:
                    status = "✅ تایید شده" if payment["status"] == "approved" else "❌ رد شده" if payment["status"] == "rejected" else "⏳ در انتظار"
                    text += f"- بسته {payment['package_type']} تایی | وضعیت: {status} | تاریخ: {payment['timestamp'][:10]}\n"
            else:
                text += "💳 هیچ سابقه پرداختی یافت نشد.\n"

            await update.message.reply_text(text, reply_markup=keyboard)

        except ValueError:
            await update.message.reply_text("لطفا یک آیدی عددی معتبر وارد کنید.")

        return True
    return False

async def admin_add_credit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """افزایش اعتبار کاربر توسط ادمین"""
    query = update.callback_query
    admin_id = query.from_user.id

    if not is_admin(admin_id):
        await query.answer("شما مجوز انجام این عملیات را ندارید.")
        return

    await query.answer()

    _, target_user_id, amount = query.data.split("_")
    target_user_id = int(target_user_id)
    amount = int(amount)

    user_data = context.application.user_data.get(target_user_id, {})
    current_credit = user_data.get("credit", FREE_MESSAGES_PER_WEEK)

    user_data["credit"] = current_credit + amount
    context.application.user_data[target_user_id] = user_data

    try:
        await context.bot.send_message(
            chat_id=target_user_id,
            text=f"✨ تبریک! {amount} پیام به اعتبار شما افزوده شد.\n"
            f"اعتبار فعلی: {user_data['credit']} پیام"
        )
    except Exception as e:
        logging.error(f"Error notifying user {target_user_id}: {e}")

    await query.edit_message_text(
        f"✅ {amount} پیام به اعتبار کاربر {target_user_id} افزوده شد.\n"
        f"اعتبار فعلی: {user_data['credit']} پیام"
    )

async def admin_overview(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش گزارش کلی برای ادمین"""
    user_id = update.message.from_user.id

    if not is_admin(user_id):
        await update.message.reply_text("شما مجوز دسترسی به این بخش را ندارید.")
        return

    payment_requests = load_requests(PAYMENT_FILE)

    total_requests = len(payment_requests)
    approved_requests = len([req for req in payment_requests if req["status"] == "approved"])
    pending_requests = len([req for req in payment_requests if req["status"] == "pending"])
    rejected_requests = len([req for req in payment_requests if req["status"] == "rejected"])

    total_revenue = sum(req["amount"] for req in payment_requests if req["status"] == "approved")

    unique_users = len(set(req["user_id"] for req in payment_requests))

    text = "📊 گزارش کلی سیستم:\n\n"
    text += f"💸 درآمد کل: {total_revenue:,} تومان\n"
    text += f"👥 تعداد کاربران منحصر به فرد: {unique_users}\n\n"
    text += f"📝 کل درخواست‌ها: {total_requests}\n"
    text += f"✅ تایید شده: {approved_requests}\n"
    text += f"⏳ در انتظار: {pending_requests}\n"
    text += f"❌ رد شده: {rejected_requests}\n"

    await update.message.reply_text(text, reply_markup=ADMIN_KEYBOARD)

async def switch_to_normal_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بازگشت به منوی عادی"""
    await update.message.reply_text(
        "بازگشت به منوی اصلی",
        reply_markup=MAIN_KEYBOARD
    )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """هندل کردن پیام‌های متنی عادی (گفتگو با AI)"""
    if await d(update, creceive_receipt_iontext):
        return

    if await receive_user_id_for_check(update, context):
        return

    if await receive_visit_receipt_id(update, context):
        return

    user_id = update.message.from_user.id
    text = update.message.text

    if is_admin(user_id):
        if text == "📋 درخواست‌های پرداخت":
            await admin_view_payments(update, context)
            return
        elif text == "🔍 وضعیت کاربر":
            await admin_check_user(update, context)
            return
        elif text == "🌐 گزارش کلی":
            await admin_overview(update, context)
            return
        elif text == "🔙 برگشت به منوی عادی":
            await switch_to_normal_menu(update, context)
            return

    if not await is_user_member_of_channel(user_id, context):
        await update.message.reply_text(
            "⚠️ لطفا ابتدا در کانال ما عضو شوید:\n"
            "https://t.me/medhoush_ir",
            reply_markup=MAIN_KEYBOARD
        )
        return

    # بررسی مکالمات فعال
    if ACTIVE_CONVERSATIONS.get(user_id):
        await receive_patient_message(update, context)
        return
    if user_id in ACTIVE_CONVERSATIONS.values():
        await receive_doctor_message(update,context)
        return

    if not await check_credit(update, context):
        return

    if text == "ℹ️ درباره ما":
        await about_us(update, context)
        return
    elif text == "📊 نمایش اعتبار فعلی":
        await show_credit(update, context)
        return
    elif text == "💳 خرید بسته":
        await buy_package(update, context)
        return
    elif text == "📄 ویزیت و نسخه پزشک":
        await visit_doctor_start(update, context)
        return
    elif text == "💬 گفتگو با پزشک":
        await start_chat_with_doctor(update, context)
        return
    elif text == "🗨️ گفتگو با مدهوش":
        await update.message.reply_text("من مدهوش هستم، دستیار هوشمند پزشکی، سوال خود را مطرح بفرمایید.", reply_markup=MAIN_KEYBOARD)
        return

    query = update.message.text
    await update.message.chat.send_action(action="typing")

    headers = {"Authorization": f"Bearer {LLM_API_KEY}", "Content-Type": "application/json"}
    data = {
        "inputs": {},
        "query": query,
        "user": str(user_id),
        "response_mode": "blocking",
        "conversation_id": context.user_data.get("conversation_id"),
        "files": [],
    }
    response = requests.post(CHAT_URL, headers=headers, json=data)
    if response.status_code == 200:
        js = response.json()
        answer = js.get("answer", "پاسخی دریافت نشد.")
        if conv := js.get("conversation_id"):
            context.user_data["conversation_id"] = conv
    else:
        answer = "❌ خطا در ارتباط با سرویس هوش مصنوعی. لطفاً بعداً تلاش کنید."
    await update.message.reply_text(
        remove_markdown(answer), reply_markup=MAIN_KEYBOARD
    )
async def receive_patient_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت عکس و ارسال به پزشک اگر چت فعال است."""
    user_id = update.message.from_user.id
    if user_id not in ACTIVE_CONVERSATIONS:
        await update.message.reply_text("لطفاً ابتدا درخواست ویزیت را ثبت و تایید کنید.")
        return

    doctor_id = ACTIVE_CONVERSATIONS[user_id]

    await update.message.chat.send_action(action="upload_photo")
    photo = await update.message.photo[-1].get_file()
    photo_path = f"photo_{user_id}.jpg"
    await photo.download_to_drive(photo_path)

    try:
        with open(photo_path, 'rb') as photo_file:
            await context.bot.send_photo(
                chat_id=doctor_id,
                photo=photo_file,
                caption=f"عکس جدید از کاربر {user_id}"
            )
        await update.message.reply_text("عکس شما به پزشک ارسال شد.", reply_markup=VISIT_KEYBOARD)
    except Exception as e:
        logging.error(f"Error sending photo to doctor {doctor_id}: {e}")
    finally:
        os.remove(photo_path)
async def receive_doctor_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت عکس و ارسال به بیماراگر چت فعال است."""
    doctor_id = update.message.from_user.id

    for id in ACTIVE_CONVERSATIONS.keys():
     if ACTIVE_CONVERSATIONS[id]== doctor_id:
      user_id=id

    await update.message.chat.send_action(action="upload_photo")
    photo = await update.message.photo[-1].get_file()
    photo_path = f"photo_{doctor_id}.jpg"
    await photo.download_to_drive(photo_path)

    try:
        with open(photo_path, 'rb') as photo_file:
            await context.bot.send_photo(
                chat_id=user_id,
                photo=photo_file,
                caption=f"عکس جدید از پزشک"
            )
        await update.message.reply_text("عکس شما به بیمار ارسال شد.", reply_markup=VISIT_KEYBOARD)
    except Exception as e:
        logging.error(f"Error sending photo to doctor {user_id}: {e}")
    finally:
        os.remove(photo_path)

async def receive_patient_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت صوت و ارسال به پزشک اگر چت فعال است."""
    user_id = update.message.from_user.id
    if user_id not in ACTIVE_CONVERSATIONS:
        await update.message.reply_text("لطفاً ابتدا درخواست ویزیت را ثبت و تایید کنید.")
        return

    doctor_id = ACTIVE_CONVERSATIONS[user_id]

    await update.message.chat.send_action(action="upload_audio")
    voice = await update.message.voice.get_file()
    audio_path = f"audio_{user_id}.ogg"
    await voice.download_to_drive(audio_path)

    try:
        with open(audio_path, 'rb') as audio_file:
            await context.bot.send_voice(
                chat_id=doctor_id,
                voice=audio_file,
                caption=f"پیام صوتی جدید از کاربر {user_id}"
            )
        await update.message.reply_text("پیام صوتی شما به پزشک ارسال شد.", reply_markup=VISIT_KEYBOARD)
    except Exception as e:
        logging.error(f"Error sending audio to doctor {doctor_id}: {e}")
    finally:
        os.remove(audio_path)

async def receive_doctor_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت صوت و ارسال به پزشک اگر چت فعال است."""
    doctor_id = update.message.from_user.id

    for id in ACTIVE_CONVERSATIONS.keys():
     if ACTIVE_CONVERSATIONS[id]== doctor_id:
      user_id=id
    

    await update.message.chat.send_action(action="upload_audio")
    voice = await update.message.voice.get_file()
    audio_path = f"audio_{doctor_id}.ogg"
    await voice.download_to_drive(audio_path)

    try:
        with open(audio_path, 'rb') as audio_file:
            await context.bot.send_voice(
                chat_id=user_id,
                voice=audio_file,
                caption=f"پیام صوتی جدید از پزشک "
            )
        await update.message.reply_text("پیام صوتی شما به بیمار ارسال شد.", reply_markup=VISIT_KEYBOARD)
    except Exception as e:
        logging.error(f"Error sending audio to doctor {user_id}: {e}")
    finally:
        os.remove(audio_path)
async def receive_doctor_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت سند و ارسال به بیمار اگر چت فعال است."""
    doctor_id = update.message.from_user.id

    for id in ACTIVE_CONVERSATIONS.keys():
     if ACTIVE_CONVERSATIONS[id]== doctor_id:
      user_id=id
    

    await update.message.chat.send_action(action="upload_document")
    doc = await update.message.document.get_file()
    ext = os.path.splitext(update.message.document.file_name)[1]
    document_path = f"doc_{user_id}{ext}"
    await doc.download_to_drive(document_path)

    try:
        with open(document_path, 'rb') as document_file:
            await context.bot.send_document(
                chat_id=user_id,
                voice=document_file,
                caption=f"پیام  جدید از پزشک "
            )
        await update.message.reply_text("پیام صوتی شما به بیمار ارسال شد.", reply_markup=VISIT_KEYBOARD)
    except Exception as e:
        logging.error(f"Error sending audio to doctor {user_id}: {e}")
    finally:
        os.remove(document_path)
async def receive_patient_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت سند و ارسال به پزشک اگر چت فعال است."""
    doctor_id = update.message.from_user.id

    user_id = update.message.from_user.id
    if user_id not in ACTIVE_CONVERSATIONS:
        await update.message.reply_text("لطفاً ابتدا درخواست ویزیت را ثبت و تایید کنید.")
        return

    doctor_id = ACTIVE_CONVERSATIONS[user_id]
    

    await update.message.chat.send_action(action="upload_document")
    doc = await update.message.document.get_file()
    ext = os.path.splitext(update.message.document.file_name)[1]
    document_path = f"doc_{user_id}{ext}"

    try:
        with open(document_path, 'rb') as document_file:
            await context.bot.send_document(
                chat_id=user_id,
                voice=documnet_file,
                caption=f"پیام  جدید از پزشک "
            )
        await update.message.reply_text("پیام صوتی شما به بیمار ارسال شد.", reply_markup=VISIT_KEYBOARD)
    except Exception as e:
        logging.error(f"Error sending audio to doctor {user_id}: {e}")
    finally:
        os.remove(document_path)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت عکس و ارسال به مقصد درست"""
    user_id = update.message.from_user.id


    
    # بررسی مکالمه با پزشک
    if user_id in ACTIVE_CONVERSATIONS:
        await receive_patient_photo(update, context)
        return
    if user_id in DOCTOR_IDS:
        await receive_doctor_photo(update, context)
        return


    # اگر مکالمه با پزشک فعال نباشد، پردازش تصویر با مدل
    if not await is_user_member_of_channel(user_id, context):
        await update.message.reply_text(
            "⚠️ لطفا ابتدا در کانال ما عضو شوید:\nhttps://t.me/medhoush_ir",
            reply_markup=MAIN_KEYBOARD
        )
        return
    if not await check_credit(update, context):
        return
    # ادامه فرآیند ارسال به مدل
    await update.message.chat.send_action(action="upload_photo")
    photo = await update.message.photo[-1].get_file()
    photo_path = f"photo_{user_id}.jpg"
    await photo.download_to_drive(photo_path)
    upload_id = await upload_file(photo_path, user_id, file_type="image")
    os.remove(photo_path)
    if not upload_id:
        await update.message.reply_text("❌ خطا در آپلود عکس. لطفا دوباره تلاش کنید.", reply_markup=MAIN_KEYBOARD)
        return
    await update.message.chat.send_action(action="typing")
    api_resp = await call_llm_api(
        user_id=user_id,
        query="لطفا این تصویر را تحلیل کنید",
        conversation_id=context.user_data.get("conversation_id"),
        upload_file_id=upload_id,
        file_type="image"
    )
    if cid := api_resp.get("conversation_id"):
        context.user_data["conversation_id"] = cid
    await update.message.reply_text(
        remove_markdown(api_resp.get("response", "خطایی رخ داده.")),
        reply_markup=MAIN_KEYBOARD
    )

async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت صوت و ارسال به مقصد درست"""
    user_id = update.message.from_user.id

    # بررسی مکالمه با پزشک
    if user_id in ACTIVE_CONVERSATIONS:
        await receive_patient_audio(update, context)
        return
    if user_id in DOCTOR_IDS:
        await receive_doctor_audio(update,context)
        return

    # اگر مکالمه با پزشک فعال نباشد، پردازش صوت با مدل
    if not await is_user_member_of_channel(user_id, context):
        await update.message.reply_text(
            "⚠️ لطفا ابتدا در کانال ما عضو شوید:\nhttps://t.me/medhoush_ir",
            reply_markup=MAIN_KEYBOARD
        )
        return
    if not await check_credit(update, context):
        return
    # ادامه فرآیند ارسال به مدل
    await update.message.chat.send_action(action="record_voice")
    voice = await update.message.voice.get_file()
    audio_path = f"audio_{user_id}.ogg"
    await voice.download_to_drive(audio_path)
    transcript = await transcribe_audio(audio_path)
    os.remove(audio_path)
    if not transcript:
        await update.message.reply_text("❌ خطا در تبدیل صوت. لطفا دوباره تلاش کنید.", reply_markup=MAIN_KEYBOARD)
        return
    await update.message.chat.send_action(action="typing")
    api_resp = await call_llm_api(
        user_id=user_id,
        query=transcript,
        conversation_id=context.user_data.get("conversation_id")
    )
    if cid := api_resp.get("conversation_id"):
        context.user_data["conversation_id"] = cid
    await update.message.reply_text(
        remove_markdown(api_resp.get("response", "خطایی رخ داده.")),
        reply_markup=MAIN_KEYBOARD
    )

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت فایل مستند، آپلود و ارسال به AI"""
    user_id = update.message.from_user.id      


    
    # بررسی مکالمه با پزشک
    if user_id in ACTIVE_CONVERSATIONS:
        await receive_patient_document(update, context)
        return
    if user_id in DOCTOR_IDS:
        await receive_doctor_document(update, context)
        return
    if not await is_user_member_of_channel(user_id, context):
        await update.message.reply_text(
            "⚠️ لطفا ابتدا در کانال ما عضو شوید:\nhttps://t.me/medhoush_ir",
            reply_markup=MAIN_KEYBOARD
        )
        return
    if not await check_credit(update, context):
        return
    await update.message.chat.send_action(action="upload_document")
    doc = await update.message.document.get_file()
    ext = os.path.splitext(update.message.document.file_name)[1]
    doc_path = f"doc_{user_id}{ext}"
    await doc.download_to_drive(doc_path)
    upload_id = await upload_file(doc_path, user_id, file_type="document")
    os.remove(doc_path)
    if not upload_id:
        await update.message.reply_text("❌ خطا در آپلود فایل. لطفا دوباره تلاش کنید.", reply_markup=MAIN_KEYBOARD)
        return
    await update.message.chat.send_action(action="typing")
    api_resp = await call_llm_api(
        user_id=user_id,
        query="لطفا این سند را تحلیل کن",
        conversation_id=context.user_data.get("conversation_id"),
        upload_file_id=upload_id,
        file_type="document"
    )
    if cid := api_resp.get("conversation_id"):
        context.user_data["conversation_id"] = cid
    await update.message.reply_text(
        remove_markdown(api_resp.get("response", "خطایی رخ داده.")),
        reply_markup=MAIN_KEYBOARD
    )

async def visit_doctor_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """شروع فرآیند ویزیت دکتر"""
    user_id = update.message.from_user.id
    await update.message.reply_text(
        "برای ویزیت توسط پزشک و ارسال پیام، لطفا ابتدا از طریق لینک زیر مبلغ مورد نظر را پرداخت کنید و شناسه پرداخت خود را ارسال نمایید:\n"
        f"{VISIT_PAY_LINK}",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📑 ارسال شناسه پرداخت", callback_data="visit_submit_receipt")],
            [InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data="back_to_main_menu")]
        ])
    )

async def visit_submit_receipt_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """هندلر ارسال شناسه پرداخت ویزیت"""
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        "لطفا شناسه پرداخت خود را وارد کنید:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ لغو", callback_data="back_to_main_menu")]
        ])
    )
    context.user_data["waiting_for_visit_receipt"] = True

async def receive_visit_receipt_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت شناسه پرداخت ویزیت و تایید توسط ادمین"""
    if context.user_data.get("waiting_for_visit_receipt"):
        receipt_id = update.message.text
        user_id = update.message.from_user.id
        username = update.message.from_user.username or "بدون نام‌کاربری"

        request_id = add_payment_request(user_id, username, "visit", 0, receipt_id, VISIT_PAYMENT_FILE)

        del context.user_data["waiting_for_visit_receipt"]

        await update.message.reply_text(
            f"✅ درخواست ویزیت شما با شماره پیگیری #{request_id} ثبت شد.\n\n"
            "پس از بررسی و تایید توسط ادمین، میتوانید با پزشک مکالمه داشته باشید.\n"
            "این فرایند معمولاً در کمتر از ۲۴ ساعت انجام می‌شود.",
            reply_markup=MAIN_KEYBOARD
        )

        for admin_id in ADMIN_IDS:
            try:
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ تایید", callback_data=f"approve_visit_{request_id}")],
                    [InlineKeyboardButton("❌ رد", callback_data=f"reject_visit_{request_id}")]
                ])

                await context.bot.send_message(
                    chat_id=admin_id,
                    text=f"🔔 درخواست ویزیت جدید:\n\n"
                    f"شناسه درخواست: #{request_id}\n"
                    f"کاربر: {username} (ID: {user_id})\n"
                    f"شناسه پرداخت: {receipt_id}\n"
                    f"زمان: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                    "لطفا این درخواست را بررسی و تایید یا رد کنید.",
                    reply_markup=keyboard
                )
            except Exception as e:
                logging.error(f"Error notifying admin {admin_id}: {e}")

        return True
    return False

async def visit_payment_action_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """هندلر تایید یا رد درخواست ویزیت"""
    query = update.callback_query
    admin_id = query.from_user.id

    if not is_admin(admin_id):
        await query.answer("شما مجوز انجام این عملیات را ندارید.")
        return

    await query.answer()

    if query.data.startswith("approve_visit_") or query.data.startswith("reject_visit_"):
        print("VISIIIIITTTTTTTT")
        prefix, action, request_id_str = query.data.split("_")
        request_id = int(request_id_str)

        requests = load_requests(VISIT_PAYMENT_FILE)
        request = None

        for req in requests:
            if req["id"] == request_id:
                request = req
                break

        if not request:
            await query.edit_message_text("❌ درخواست مورد نظر یافت نشد.")
            return

        user_id = request["user_id"]

        if prefix == "approve":
            update_payment_status(request_id, "approved", admin_id, VISIT_PAYMENT_FILE)

            try:
                ACTIVE_CONVERSATIONS[user_id] = DOCTOR_IDS[0]
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"✅ درخواست ویزیت شما با شناسه #{request_id} تایید شد!\n\n"
                    "اکنون می‌توانید با پزشک مکالمه داشته باشید.",
                    reply_markup=VISIT_KEYBOARD
                )

                await query.edit_message_text(
                    f"✅ درخواست ویزیت #{request_id} با موفقیت تایید شد."
                )
            except Exception as e:
                logging.error(f"Error approving visit payment: {e}")
                await query.edit_message_text(
                    f"❌ خطا در تایید درخواست ویزیت #{request_id}:\n{str(e)}"
                )

        elif prefix == "reject":
            update_payment_status(request_id, "rejected", admin_id, VISIT_PAYMENT_FILE)

            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"❌ متاسفانه درخواست ویزیت شما با شناسه #{request_id} تایید نشد.\n\n"
                    "لطفا برای بررسی با پشتیبانی تماس بگیرید یا مجددا تلاش کنید.",
                    reply_markup=MAIN_KEYBOARD
                )

                await query.edit_message_text(
                    f"❌ درخواست ویزیت #{request_id} رد شد."
                )
            except Exception as e:
                logging.error(f"Error rejecting visit payment: {e}")
                await query.edit_message_text(
                    f"❌ خطا در رد درخواست ویزیت #{request_id}:\n{str(e)}"
                )

async def start_chat_with_doctor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """شروع مکالمه با پزشک"""
    user_id = update.message.from_user.id
    if user_id in ACTIVE_CONVERSATIONS:
        await update.message.reply_text("مکالمه با پزشک آغاز شده است. پیام‌های خود را ارسال کنید.\nبرای پایان مکالمه، 'اتمام گفتگو' بگویید.", reply_markup=VISIT_KEYBOARD)
    else:
        await update.message.reply_text("لطفاً ابتدا درخواست ویزیت را ثبت کنید.")

async def receive_patient_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پروسه مکالمه با پزشک"""
    user_id = update.message.from_user.id
    if user_id not in ACTIVE_CONVERSATIONS:
        await update.message.reply_text("لطفاً ابتدا درخواست ویزیت را ثبت و تایید کنید.")
        return
    if user_id in DOCTOR_IDS:
        await receive_doctor_message(update , context)
    doctor_id = ACTIVE_CONVERSATIONS[user_id]
    user_message = update.message.text
    user_name = update.message.from_user.username or "بدون نام‌کاربری"

    if user_message.lower().strip() in ["اتمام گفتگو", "پایان"]:
        await update.message.reply_text("مکالمه با پزشک به پایان رسید.", reply_markup=MAIN_KEYBOARD)
        del ACTIVE_CONVERSATIONS[user_id]
        return

    try:
        await context.bot.send_message(
            chat_id=doctor_id,
            text=f"پیامی جدید از {user_name}:\n\n{user_message}"
        )
        await update.message.reply_text("پیام شما به پزشک ارسال شد.", reply_markup=VISIT_KEYBOARD)
    except Exception as e:
        logging.error(f"Error sending message to doctor {doctor_id}: {e}")



async def receive_doctor_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت پیام‌های ارسالی پزشک برای کاربر"""
    doctor_id = update.message.from_user.id
    doctor_message = update.message.text

    for user_id, active_doctor_id in ACTIVE_CONVERSATIONS.items():
        if active_doctor_id == doctor_id:
            try:
                if doctor_message.lower().strip() in ["اتمام گفتگو", "پایان"]:
                            await update.message.reply_text("مکالمه پایان یافت", reply_markup=MAIN_KEYBOARD)
                            await context.bot.send_message(
                            chat_id=user_id,
                            text=f"مکالمه توسط پزشک پایان یافت"
                        )
                            del ACTIVE_CONVERSATIONS[user_id]
                            return

                else:  
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=f"پیامی از پزشک:\n\n{doctor_message}"
                    )
            except Exception as e:
                logging.error(f"Error sending message to user {user_id}: {e}")

# ----------------------------
# تابع اصلی
# ----------------------------
def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", lambda update, context: start(update, context) if is_admin(update.message.from_user.id) else None))

    app.add_handler(MessageHandler(filters.Regex("^ℹ️ درباره ما$"), about_us))
    app.add_handler(MessageHandler(filters.Regex("^📊 نمایش اعتبار فعلی$"), show_credit))
    app.add_handler(MessageHandler(filters.Regex("^💳 خرید بسته$"), buy_package))
    app.add_handler(MessageHandler(filters.Regex("^🗨️ گفتگو با مدهوش$"), handle_text))
    app.add_handler(MessageHandler(filters.Regex("^📄 ویزیت و نسخه پزشک$"), visit_doctor_start))
    app.add_handler(MessageHandler(filters.Regex("^💬 گفتگو با پزشک$"), start_chat_with_doctor))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    app.add_handler(MessageHandler(filters.TEXT & filters.User(DOCTOR_IDS), receive_doctor_message))

    app.add_handler(CallbackQueryHandler(submit_receipt_handler, pattern="^submit_receipt$"))
    app.add_handler(CallbackQueryHandler(package_selection_handler, pattern="^package_"))
    app.add_handler(CallbackQueryHandler(package_selection_handler, pattern="^cancel_receipt$"))
    app.add_handler(CallbackQueryHandler(payment_action_handler, pattern="^approve1_|^reject1_"))
    app.add_handler(CallbackQueryHandler(admin_add_credit, pattern="^add_credit_"))
    app.add_handler(CallbackQueryHandler(visit_submit_receipt_handler, pattern="^visit_submit_receipt$"))
    app.add_handler(CallbackQueryHandler(visit_payment_action_handler, pattern="^approve_visit_|^reject_visit_"))
    app.add_handler(CallbackQueryHandler(switch_to_normal_menu, pattern="^back_to_main_menu$"))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.VOICE, handle_audio))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))

    logging.info("Bot started.")
    app.run_polling()
    
if __name__ == "__main__":
    main()
