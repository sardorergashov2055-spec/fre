"""Optimallashtirilgan bot runtime.

Maqsad:
 - Logging minimal: faqat ishga tushish va xatolar.
 - Resilient wrappers: Telegram API chaqiruvlarida network errorlar (WinError 10054) ni
   swallow qilib, worker thread crashlarini oldini olish.
 - Background threads: payment detection va deposit bajarish asinxron (blok qilmaydi).
 - Channel-only notifications: To'lov kanali/admin DM spam yo'q, faqat NOTIFICATION_CHANNEL.

Tavsiya:
 - Production'da main.py o'rniga shu main_optimized.py ni ishga tushiring.
"""

import telebot
from telebot import apihelper
from telebot.types import Message
import re
from database.database import db
from handlers.start import register_start_handlers
from handlers.menu import register_menu_handlers
from handlers.deposit import register_deposit_handlers, execute_deposit
from handlers.withdrawal import register_withdrawal_handlers
from handlers.admin import register_admin_handlers
from handlers.payments import register_payment_handlers
from handlers.payment_detector import PaymentDetector
from config import BOT_TOKEN
import config


# Middleware'ni yoqish
apihelper.ENABLE_MIDDLEWARE = True

bot = telebot.TeleBot(BOT_TOKEN)


# Middleware: Bot o'chirilganda faqat admin ishlashi mumkin
@bot.middleware_handler(update_types=['message'])
def check_bot_active(bot_instance, message):
    """Bot o'chirilganda faqat admin private chatda ishlashi, guruhlarda esa detektor ishlashi uchun ruxsat."""
    if not config.BOT_ACTIVE:
        # Faqat private chatdagi foydalanuvchilarni bloklaymiz (admindan tashqari)
        try:
            chat_type = getattr(message.chat, 'type', 'private')
            user_id = getattr(message.from_user, 'id', None)
        except Exception:
            chat_type = 'private'
            user_id = None

        if chat_type == 'private' and user_id != config.ADMIN_ID:
            try:
                # Oddiy matn, hech qanday tugma/keyboard yo'q - ReplyKeyboardRemove bilan tugmalarni olib tashlaymiz
                from telebot.types import ReplyKeyboardRemove
                bot.send_message(
                    message.chat.id,
                    "🚫 Bot hozirda texnik ishlar olib borilmoqda. Keyinroq urinib ko'ring.",
                    reply_markup=ReplyKeyboardRemove()
                )
            except Exception:
                pass
            return  # Xabarni boshqa handlerlar ko'rib chiqmasin
    # Agar bot aktiv yoki admin bo'lsa yoki guruh/kanal bo'lsa, davom etadi


# Handlerlarni ro'yxatga olish
register_start_handlers(bot)
register_menu_handlers(bot)
register_deposit_handlers(bot)
register_withdrawal_handlers(bot)
register_admin_handlers(bot)
register_payment_handlers(bot)

# MUHIM: Admin manual deposit callback handlerini import qilish
# Bu handler qo'lda to'ldirish tasdiqlashini boshqaradi
try:
    from handlers.admin import admin_states
except Exception:
    admin_states = {}


# Payment detector
payment_detector = PaymentDetector(db)

# Pre-compile lambda uchun - tezroq
def _is_payment_message(m):
    """TEZKOR check - payment xabari yoki yo'q"""
    text = getattr(m, 'text', None) or getattr(m, 'caption', None)
    if not text:
        return False
    # Faqat PAYMENT so'zi borligini tekshirish - regex keyinroq
    return 'PAYMENT' in text.upper()


@bot.message_handler(
    func=_is_payment_message,
    content_types=['text', 'photo', 'video', 'document', 'animation']
)
def handle_group_payment(message: Message):
    """Guruh PAYMENT xabarini aniqlash va API chaqirish."""
    try:
        msg_text = (getattr(message, 'text', None) or getattr(message, 'caption', None) or '')
        parsed = payment_detector.parse_payment_message(msg_text)
        if not parsed:
            return

        payment = payment_detector.find_matching_payment(parsed)
        if not payment:
            return

        payment_id = getattr(payment, 'payment_id', None)
        bukmeker = getattr(payment, 'bukmeker', None)
        player_id = getattr(payment, 'player_id', None)
        amount = getattr(payment, 'amount', None)
        user_id = getattr(payment, 'user_id', None)
        status = getattr(payment, 'status', None)

        if status == 'completed' or not all([bukmeker, player_id, amount]):
            return

        try:
            from handlers.deposit import execute_deposit_detailed
            result = execute_deposit_detailed(bukmeker, player_id, amount, {})
            executed = result.get('Success', False)
            error_msg = result.get('Error') or result.get('error') or result.get('Message') or 'Noma\'lum xato'
        except Exception as e:
            executed = False
            error_msg = str(e)

        if executed:
            db.update_payment_status(payment_id, 'completed')
            
            # Notification va user xabar yuborish
            try:
                from handlers.deposit import get_balance
                balance_result = get_balance(bukmeker, player_id)
                balance_info = {'Balance': balance_result.get('Balance', 0), 'Limit': balance_result.get('Limit', 0)} if balance_result and balance_result.get('Success') else {'Balance': 0, 'Limit': 0}
                
                user_data = db.get_user(user_id)
                user_username = getattr(user_data, 'username', '') or '' if user_data else ''
                user_phone = getattr(user_data, 'phone', '') or '' if user_data else ''
                
                if getattr(config, 'NOTIFICATION_CHANNEL_ID', None):
                    username_str = f"@{user_username}" if user_username else f"ID: {user_id}"
                    phone_str = user_phone if user_phone else "—"
                    
                    channel_msg = (
                        f"✅ Operatsiya muvaffaqiyatli o'tdi!\n\n"
                        f"Bukmeker: {bukmeker}\n"
                        f"ID: {player_id}\n"
                        f"Summa: {amount:,.0f} so'm\n\n"
                        f"Mijoz: {username_str}\n"
                        f"Tel: {phone_str}\n\n"
                        f"Kassa:\n"
                        f"  Balans: {balance_info['Balance']:,.0f} so'm\n"
                        f"  Limit: {balance_info['Limit']:,.0f} so'm"
                    )
                    bot.send_message(config.NOTIFICATION_CHANNEL_ID, channel_msg)
                
                payment_msg_id = getattr(payment, 'payment_message_id', None)
                if payment_msg_id:
                    try:
                        bot.delete_message(user_id, payment_msg_id)
                    except Exception:
                        pass
                
                bot.send_message(
                    user_id,
                    f"✅ To'lov amalga oshirildi!\n\n"
                    f"Bukmeker: {bukmeker}\n"
                    f"Summa: {amount:,.0f} so'm\n\n"
                    f"Bot: @uzpaykassa_bot"
                )
            except Exception:
                pass
        else:
            if getattr(config, 'NOTIFICATION_CHANNEL_ID', None):
                error_channel_msg = (
                    f"❌ To'lov muvaffaqiyatsiz!\n\n"
                    f"Bukmeker: {bukmeker}\n"
                    f"ID: {player_id}\n"
                    f"Summa: {amount:,.0f} so'm\n\n"
                    f"Sabab: {error_msg}"
                )
                bot.send_message(config.NOTIFICATION_CHANNEL_ID, error_channel_msg)
    except Exception:
        pass



def register_cancel_callback(bot_instance: telebot.TeleBot):
    """To'lovni bekor qilish inline tugma callback'i."""
    @bot_instance.callback_query_handler(func=lambda call: call.data == 'cancel_payment')
    def cancel_payment_callback(call):
        try:
            bot_instance.edit_message_text(
                "❌ To'lov bekor qilindi.",
                call.message.chat.id,
                call.message.message_id
            )
        except Exception:
            pass


register_cancel_callback(bot)


if __name__ == "__main__":
    """Bot'ni ishga tushirish: handlerlar ro'yxatga olingan, polling boshlanadi."""
    try:
        print("🤖 Bot ishga tushmoqda...")
        print(f"📊 Admin ID: {config.ADMIN_ID}")

        users_count = db.get_users_count()
        print(f"👥 Foydalanuvchilar: {users_count}")

        import time as _time
        backoff = 1
        while True:
            try:
                # Polling sozlamalari - TEZ va BARQAROR
                bot.infinity_polling(
                    timeout=20,           # Server timeout - 20 soniya
                    long_polling_timeout=15,  # Long polling - 15 soniya
                    skip_pending=True,    # Eski xabarlarni o'tkazib yuborish
                    allowed_updates=['message', 'callback_query']  # Faqat kerakli update'lar
                )
            except KeyboardInterrupt:
                raise
            except Exception as e:
                print(f"⚠️ Polling error: {e}. Restarting in {backoff}s...")
                _time.sleep(backoff)
                backoff = min(backoff * 2, 60)
                continue
    except KeyboardInterrupt:
        print("\n🛑 Bot to'xtatildi...")
    except Exception as e:
        print(f"❌ Xatolik: {e}")
