import telebot
from telebot.types import Message, ReplyKeyboardRemove
from database.database import db
from database.models import User
from utils.keyboards import get_phone_request_keyboard, get_main_menu_keyboard, get_admin_menu_keyboard, get_main_menu_keyboard_admin
from config import ADMIN_ID
import config

user_states = {}

def register_start_handlers(bot: telebot.TeleBot):
    
    @bot.message_handler(commands=['start'])
    def start_command(message: Message):
        user_id = message.from_user.id
        
        # Admin tekshiruvi
        if user_id == ADMIN_ID:
            # Admin to'g'ridan admin panelga yo'naltiriladi
            bot.send_message(
                user_id,
                "👨‍💼 Admin panel:",
                reply_markup=get_admin_menu_keyboard()
            )
            return
        
        # Bot o'chirilgan bo'lsa, oddiy foydalanuvchilarga keyboard bermaslik
        if not config.BOT_ACTIVE:
            bot.send_message(
                user_id,
                "🚫 Bot hozirda texnik ishlar olib borilmoqda. Keyinroq urinib ko'ring.",
                reply_markup=ReplyKeyboardRemove()
            )
            return
        
        user = db.get_user(user_id)
        
        if not user:
            # Yangi foydalanuvchi
            new_user = User(
                user_id=user_id,
                username=message.from_user.username,
                first_name=message.from_user.first_name
            )
            db.add_user(new_user)
            
            bot.send_message(
                user_id,
                "👋 Assalomu alaykum! UzPaykassa botiga xush kelibsiz!\n\n"
                "📱 Davom etish uchun telefon raqamingizni yuboring:",
                reply_markup=get_phone_request_keyboard()
            )
        elif not user.phone:
            # Telefon raqam yo'q
            bot.send_message(
                user_id,
                "📱 Davom etish uchun telefon raqamingizni yuboring:",
                reply_markup=get_phone_request_keyboard()
            )
        else:
            # Ro'yxatdan o'tgan foydalanuvchi
            bot.send_message(
                user_id,
                f"👋 Xush kelibsiz, {user.first_name}!\n\n"
                "Quyidagi xizmatlardan birini tanlang:",
                reply_markup=get_main_menu_keyboard()
            )
    
    @bot.message_handler(content_types=['contact'])
    def handle_contact(message: Message):
        user_id = message.from_user.id
        
        # Bot o'chirilgan bo'lsa, contact qabul qilmaslik
        if not config.BOT_ACTIVE and user_id != ADMIN_ID:
            bot.send_message(
                user_id,
                "🚫 Bot hozirda texnik ishlar olib borilmoqda. Keyinroq urinib ko'ring.",
                reply_markup=ReplyKeyboardRemove()
            )
            return
        
        if message.contact and message.contact.user_id == user_id:
            phone = message.contact.phone_number
            
            # Telefon raqamni saqlash
            if db.update_user_phone(user_id, phone):
                bot.send_message(
                    user_id,
                    "✅ Telefon raqamingiz saqlandi!\n\n"
                    "Quyidagi xizmatlardan birini tanlang:",
                    reply_markup=get_main_menu_keyboard()
                )
            else:
                bot.send_message(
                    user_id,
                    "❌ Xatolik yuz berdi. Qaytadan urinib ko'ring."
                )
        else:
            bot.send_message(
                user_id,
                "❌ Iltimos, o'zingizning telefon raqamingizni yuboring!"
            )
