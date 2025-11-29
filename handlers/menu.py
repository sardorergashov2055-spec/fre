import telebot
from telebot.types import Message, ReplyKeyboardRemove
from utils.keyboards import (get_main_menu_keyboard, get_bookmakers_keyboard, 
                           get_urls_keyboard, get_apps_keyboard, get_admin_menu_keyboard)
import config
from utils.state_manager import last_menu_action, clear_user_states

def register_menu_handlers(bot: telebot.TeleBot):
    
    @bot.message_handler(func=lambda message: message.text == "💰 Hisob to'ldirish")
    def deposit_menu(message: Message):
        user_id = message.from_user.id
        
        # Bot o'chirilgan bo'lsa va admin emas bo'lsa, bloklash
        if not config.BOT_ACTIVE and user_id != config.ADMIN_ID:
            bot.send_message(
                message.chat.id,
                "🚫 Bot hozirda texnik ishlar olib borilmoqda. Keyinroq urinib ko'ring.",
                reply_markup=ReplyKeyboardRemove()
            )
            return
        
        last_menu_action[user_id] = 'deposit'
        
        bot.send_message(
            message.chat.id,
            "🎯 Bukmekerlar ro'yxatidan birini tanlang:",
            reply_markup=get_bookmakers_keyboard()
        )
    
    @bot.message_handler(func=lambda message: message.text == "💸 Pul yechish")
    def withdrawal_menu(message: Message):
        user_id = message.from_user.id
        
        # Bot o'chirilgan bo'lsa va admin emas bo'lsa, bloklash
        if not config.BOT_ACTIVE and user_id != config.ADMIN_ID:
            bot.send_message(
                message.chat.id,
                "🚫 Bot hozirda texnik ishlar olib borilmoqda. Keyinroq urinib ko'ring.",
                reply_markup=ReplyKeyboardRemove()
            )
            return
        
        last_menu_action[user_id] = 'withdrawal'
        
        bot.send_message(
            message.chat.id,
            "🎯 Pul yechish uchun bukmekerlar ro'yxatidan birini tanlang:",
            reply_markup=get_bookmakers_keyboard()
        )
    
    @bot.message_handler(func=lambda message: message.text == "📱 Ilovalar")
    def apps_menu(message: Message):
        user_id = message.from_user.id
        
        # Bot o'chirilgan bo'lsa va admin emas bo'lsa, bloklash
        if not config.BOT_ACTIVE and user_id != config.ADMIN_ID:
            bot.send_message(
                message.chat.id,
                "🚫 Bot hozirda texnik ishlar olib borilmoqda. Keyinroq urinib ko'ring.",
                reply_markup=ReplyKeyboardRemove()
            )
            return
        
        bot.send_message(
            message.chat.id,
            "📱 Rasmiy ilovalarni yuklab olish:",
            reply_markup=get_apps_keyboard()
        )
    
    @bot.message_handler(func=lambda message: message.text == "📞 Aloqa")
    def contact_menu(message: Message):
        user_id = message.from_user.id
        
        # Bot o'chirilgan bo'lsa va admin emas bo'lsa, bloklash
        if not config.BOT_ACTIVE and user_id != config.ADMIN_ID:
            bot.send_message(
                message.chat.id,
                "🚫 Bot hozirda texnik ishlar olib borilmoqda. Keyinroq urinib ko'ring.",
                reply_markup=ReplyKeyboardRemove()
            )
            return
        
        bot.send_message(
            message.chat.id,
            "📞 Bizning administratorlarimiz:\n\n"
            "• Texnik yordam: @admin1\n"
            "• Savollar va takliflar: @admin2\n"
            "• 24/7 onlayn yordam",
            reply_markup=get_urls_keyboard()
        )
    
    @bot.message_handler(func=lambda message: message.text == "🔙 Orqaga")
    def back_to_main(message: Message):
        user_id = message.from_user.id
        clear_user_states(user_id)
        # Admin uchun orqaga har doim admin paneliga qaytaradi
        if user_id == getattr(config, 'ADMIN_ID', None):
            bot.send_message(
                message.chat.id,
                "👨‍💼 Admin panel:",
                reply_markup=get_admin_menu_keyboard()
            )
        else:
            bot.send_message(
                message.chat.id,
                "🏠 Asosiy menyu:",
                reply_markup=get_main_menu_keyboard()
            )
