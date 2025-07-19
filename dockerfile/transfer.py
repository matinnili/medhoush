
class Transfer(ABC):


    def __init__(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ایجاد یک شیء انتقال با به‌روزرسانی و زمینه."""
        self.update = update
        self.context = context

    @abstractmethod
    def extract_ids(self):
        
        NotImplementedError("This method should be implemented by subclasses.")
    @abstractmethod
    async def upload(self):
        
        NotImplementedError("This method should be implemented by subclasses.")
    @abstractmethod
    async def send(self):
        
        
        NotImplementedError("This method should be implemented by subclasses.")

class TransferClassFactory():
    def __init__(self, update: Update, context: ContextTypes.DEFAULT_TYPE,role: str,type):
        """ایجاد یک شیء انتقال بر اساس نقش."""
        self.update = update
        self.context = context
        self.role = role
        self.type = type
    def get_transfer_class(self):
        """بازگشت کلاس انتقال بر اساس نقش."""
        if self.role == "doctor":
            if self.type == "photo":
                return DoctorPhotoTransfer(self.update, self.context)
            elif self.type == "audio":
                return DoctorAudioTransfer(self.update, self.context)
            elif self.type == "document":
                return DoctorDocumentTransfer(self.update, self.context)
        elif self.role == "patient":
            if self.type == "photo":
                return PatientPhotoTransfer(self.update, self.context)
            elif self.type == "audio":
                return PatientAudioTransfer(self.update, self.context)
            elif self.type == "document":
                return PatientDocumentTransfer(self.update, self.context)
        else:
            raise ValueError("Invalid role or type specified.")
    
class DoctorPhotoransfer(Transfer):

    def __init__(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
       
        super().__init__(update, context)

    def extract_ids(self):
        """استخراج شناسه پزشک و بیمار از به‌روزرسانی."""
        user_id = self.update.message.from_user.id
        for id in ACTIVE_CONVERSATIONS:
            if ACTIVE_CONVERSATIONS[id] == user_id:
                return id, user_id
        raise ValueError("No active conversation found for the doctor.")

    async def upload(self):
        """بارگذاری عکس پزشک و ذخیره آن در مسیر مشخص."""
        patient_id, doctor_id = self.extract_ids()
        await self.update.message.chat.send_action(action="upload_photo")
        photo = await self.update.message.photo[-1].get_file()
        photo_path = f"photo_{user_id}.jpg"

        try:
            await photo.download_to_drive(photo_path)
            return photo_path
        except Exception as e:
            logging.error(f"Error downloading photo: {e}")
            raise

    async def send(self):
        """ارسال عکس بارگذاری شده به بیمار."""
        patient_id, doctor_id = self.extract_ids()
        photo_path = await self.upload()

        try:
            await self.context.bot.send_photo(
                chat_id=patient_id,
                photo=open(photo_path, 'rb'),
                caption="عکس شما توسط پزشک ارسال شد."
            )
            await self.update.message.reply_text("عکس شما به بیمار ارسال شد.")
        except Exception as e:
            logging.error(f"Error sending photo to patient {patient_id}: {e}")
        finally:
            os.remove(photo_path)


class DoctorAudioTransfer(Transfer):

    def __init__(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        super().__init__(update, context)

    def extract_ids(self):
        """استخراج شناسه پزشک و بیمار از به‌روزرسانی."""
        user_id = self.update.message.from_user.id
        for id in ACTIVE_CONVERSATIONS:
            if ACTIVE_CONVERSATIONS[id] == user_id:
                return id, user_id
        raise ValueError("No active conversation found for the doctor.")

    async def upload(self):
        """بارگذاری فایل صوتی پزشک و ذخیره آن در مسیر مشخص."""
        patient_id, doctor_id = self.extract_ids()
        await self.update.message.chat.send_action(action="upload_voice")
        audio = await self.update.message.voice.get_file()
        audio_path = f"audio_{user_id}.ogg"

        try:
            await audio.download_to_drive(audio_path)
            return audio_path
        except Exception as e:
            logging.error(f"Error downloading audio: {e}")
            raise

    async def send(self):
        """ارسال فایل صوتی بارگذاری شده به بیمار."""
        patient_id, doctor_id = self.extract_ids()
        audio_path = await self.upload()

        try:
            with open(audio_path, 'rb') as audio_file:
                await self.context.bot.send_voice(
                    chat_id=patient_id,
                    voice=audio_file,
                    caption="پیام صوتی شما توسط پزشک ارسال شد."
                )
            await self.update.message.reply_text("پیام صوتی شما به بیمار ارسال شد.")
        except Exception as e:
            logging.error(f"Error sending audio to patient {patient_id}: {e}")
        finally:
            os.remove(audio_path)

class DoctorDocumentTransfer(Transfer):

    def __init__(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        super().__init__(update, context)

    def extract_ids(self):
        """استخراج شناسه پزشک و بیمار از به‌روزرسانی."""
        user_id = self.update.message.from_user.id
        for id in ACTIVE_CONVERSATIONS:
            if ACTIVE_CONVERSATIONS[id] == user_id:
                return id, user_id
        raise ValueError("No active conversation found for the doctor.")

    async def upload(self):
        """بارگذاری سند پزشک و ذخیره آن در مسیر مشخص."""
        patient_id, doctor_id = self.extract_ids()
        await self.update.message.chat.send_action(action="upload_document")
        doc = await self.update.message.document.get_file()
        ext = os.path.splitext(update.message.document.file_name)[1]
        document_path = f"doc_{user_id}{ext}"

        try:
            await doc.download_to_drive(document_path)
            return document_path
        except Exception as e:
            logging.error(f"Error downloading document: {e}")
            raise

    async def send(self):
        """ارسال سند بارگذاری شده به بیمار."""
        patient_id, doctor_id = self.extract_ids()
        document_path = await self.upload()

        try:
            with open(document_path, 'rb') as document_file:
                await self.context.bot.send_document(
                    chat_id=patient_id,
                    document=document_file,
                    caption="سند شما توسط پزشک ارسال شد."
                )
            await self.update.message.reply_text("سند شما به بیمار ارسال شد.")
        except Exception as e:
            logging.error(f"Error sending document to patient {patient_id}: {e}")
        finally:
            os.remove(document_path)

class PatientPhotoTransfer(Transfer):

    def __init__(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        super().__init__(update, context)

    def extract_ids(self):
        """استخراج شناسه بیمار و پزشک از به‌روزرسانی."""
        user_id = self.update.message.from_user.id
        if user_id not in ACTIVE_CONVERSATIONS:
            raise ValueError("No active conversation found for the patient.")
        doctor_id = ACTIVE_CONVERSATIONS[user_id]
        return user_id, doctor_id

    async def upload(self):
        """بارگذاری عکس بیمار و ذخیره آن در مسیر مشخص."""
        user_id, doctor_id = self.extract_ids()
        await self.update.message.chat.send_action(action="upload_photo")
        photo = await self.update.message.photo[-1].get_file()
        photo_path = f"photo_{user_id}.jpg"

        try:
            await photo.download_to_drive(photo_path)
            return photo_path
        except Exception as e:
            logging.error(f"Error downloading photo: {e}")
            raise

    async def send(self):
        """ارسال عکس بارگذاری شده به پزشک."""
        user_id, doctor_id = self.extract_ids()
        photo_path = await self.upload()

        try:
            with open(photo_path, 'rb') as photo_file:
                await self.context.bot.send_photo(
                    chat_id=doctor_id,
                    photo=photo_file,
                    caption="عکس شما توسط بیمار ارسال شد."
                )
            await self.update.message.reply_text("عکس شما به پزشک ارسال شد.")
        except Exception as e:
            logging.error(f"Error sending photo to doctor {doctor_id}: {e}")
        finally:
            os.remove(photo_path)

class PatientAudioTransfer(Transfer):

    def __init__(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        super().__init__(update, context)

    def extract_ids(self):
        """استخراج شناسه بیمار و پزشک از به‌روزرسانی."""
        user_id = self.update.message.from_user.id
        if user_id not in ACTIVE_CONVERSATIONS:
            raise ValueError("No active conversation found for the patient.")
        doctor_id = ACTIVE_CONVERSATIONS[user_id]
        return user_id, doctor_id

    async def upload(self):
        """بارگذاری فایل صوتی بیمار و ذخیره آن در مسیر مشخص."""
        user_id, doctor_id = self.extract_ids()
        await self.update.message.chat.send_action(action="upload_voice")
        audio = await self.update.message.voice.get_file()
        audio_path = f"audio_{user_id}.ogg"

        try:
            await audio.download_to_drive(audio_path)
            return audio_path
        except Exception as e:
            logging.error(f"Error downloading audio: {e}")
            raise

    async def send(self):
        """ارسال فایل صوتی بارگذاری شده به پزشک."""
        user_id, doctor_id = self.extract_ids()
        audio_path = await self.upload()

        try:
            with open(audio_path, 'rb') as audio_file:
                await self.context.bot.send_voice(
                    chat_id=doctor_id,
                    voice=audio_file,
                    caption="پیام صوتی شما توسط بیمار ارسال شد."
                )
            await self.update.message.reply_text("پیام صوتی شما به پزشک ارسال شد.")
        except Exception as e:
            logging.error(f"Error sending audio to doctor {doctor_id}: {e}")
        finally:
            os.remove(audio_path)


class PatientDocumentTransfer(Transfer):
    def __init__(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        super().__init__(update, context)
    def extract_ids(self):
        """استخراج شناسه بیمار و پزشک از به‌روزرسانی."""
        user_id = self.update.message.from_user.id
        if user_id not in ACTIVE_CONVERSATIONS:
            raise ValueError("No active conversation found for the patient.")
        doctor_id = ACTIVE_CONVERSATIONS[user_id]
        return user_id, doctor_id           
    async def upload(self):
        """بارگذاری سند بیمار و ذخیره آن در مسیر مشخص."""
        user_id, doctor_id = self.extract_ids()
        await self.update.message.chat.send_action(action="upload_document")
        doc = await self.update.message.document.get_file()
        ext = os.path.splitext(self.update.message.document.file_name)[1]
        document_path = f"doc_{user_id}{ext}"

        try:
            await doc.download_to_drive(document_path)
            return document_path
        except Exception as e:
            logging.error(f"Error downloading document: {e}")
            raise       
    async def send(self):
        """ارسال سند بارگذاری شده به پزشک."""
        user_id, doctor_id = self.extract_ids()
        document_path = await self.upload()

        try:
            with open(document_path, 'rb') as document_file:
                await self.context.bot.send_document(
                    chat_id=doctor_id,
                    document=document_file,
                    caption="سند شما توسط بیمار ارسال شد."
                )
            await self.update.message.reply_text("سند شما به پزشک ارسال شد.")
        except Exception as e:
            logging.error(f"Error sending document to doctor {doctor_id}: {e}")
        finally:
            os.remove(document_path)


