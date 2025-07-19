from utils import (
    is_user_member_of_channel,

class FileHandler(ABC):
    def __init__(context,update):
        self.context = context
        self.update = update
    @abstractmethod
    def initial_check(self):
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
