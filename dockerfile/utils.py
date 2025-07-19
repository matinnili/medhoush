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