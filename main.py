from handlers.payment_detector import PaymentDetector
from datetime import datetime
import re
import telebot
from telebot import apihelper
from telebot.types import Message
import config
from database.database import db
from handlers.start import register_start_handlers
from handlers.menu import register_menu_handlers
from handlers.deposit import register_deposit_handlers, register_cancel_callback, get_balance
from handlers.withdrawal import register_withdrawal_handlers
from handlers.admin import register_admin_handlers
from handlers.payments import register_payment_handlers
from handlers.deposit import execute_deposit
from utils.keyboards import get_main_menu_keyboard, get_admin_menu_keyboard
from utils.helpers import create_channel_payment_message
from utils.state_manager import is_user_in_process

# Middleware ni yoqish
apihelper.ENABLE_MIDDLEWARE = True

# Bot yaratish
bot = telebot.TeleBot(config.BOT_TOKEN)

# Wrap core bot methods with safe wrappers to prevent network errors from
# bubbling up and crashing TeleBot worker threads (ConnectionResetError etc.).
import requests
import os

def _maybe_log_swallowed(kind: str, message: str) -> None:
    """Best-effort minimal logger for swallowed network errors.

    Writes a short line to logs/swallowed.log without raising if logging fails.
    """
    try:
        log_dir = os.path.join(os.getcwd(), 'logs')
        os.makedirs(log_dir, exist_ok=True)
        with open(os.path.join(log_dir, 'swallowed.log'), 'a', encoding='utf-8') as f:
            # keep it one line; include timestamp and kind
            from datetime import datetime as _dt
            f.write(f"{_dt.now().isoformat()} | {kind} | {message}\n")
    except Exception:
        pass

# Patch instance methods used throughout the codebase.
# Capture originals and wrap them. Using the bound original avoids 'self' issues.
orig_send = bot.send_message
orig_reply = bot.reply_to
orig_edit_text = bot.edit_message_text
orig_edit_markup = bot.edit_message_reply_markup

def _wrap(orig):
    def _safe(*args, **kwargs):
        try:
            return orig(*args, **kwargs)
        except requests.exceptions.RequestException as e:
            _maybe_log_swallowed('network', str(e))
            return None
        except Exception as e:
            _maybe_log_swallowed('unexpected', str(e))
            return None
    return _safe


bot.send_message = _wrap(orig_send)
bot.reply_to = _wrap(orig_reply)
bot.edit_message_text = _wrap(orig_edit_text)
bot.edit_message_reply_markup = _wrap(orig_edit_markup)

# Handlerlarni ro'yxatga olish
register_start_handlers(bot)
register_menu_handlers(bot)
register_deposit_handlers(bot)
register_withdrawal_handlers(bot)
register_admin_handlers(bot)
register_payment_handlers(bot)
register_cancel_callback(bot)

# Payment detector for group/channel payment notifications
payment_detector = PaymentDetector(db)


@bot.message_handler(func=lambda message: bool(re.search(r'PAYMENT\|', (message.text or ''), re.IGNORECASE)), content_types=['text'])
def handle_group_payment(message: Message):
    try:
        # Fast parse; heavy work runs in background to avoid blocking telebot workers
        parsed = payment_detector.parse_payment_message(message.text or '')
        if not parsed:
            return

        # Do NOT send any message back to the group where the detector saw the payment.
        # We'll notify only the admin/notification channel to avoid group spam.

        def _bg_detect_and_handle(parsed_msg, orig_message):
            try:
                payment = payment_detector.find_matching_payment(parsed_msg)
                if not payment:
                    return

                # mark completed in DB, but only notify admin/group if this is the first time
                try:
                    payment_id = getattr(payment, 'payment_id', None)
                    # Load current DB record to see current status
                    existing = db.get_payment_by_id(payment_id)
                    already_completed = getattr(existing, 'status', None) == 'completed'

                    # Update status to completed (idempotent)
                    db.update_payment_status(payment_id, 'completed')
                except Exception:
                    existing = None
                    already_completed = False

                # Notify admin only if this payment wasn't already completed
                # No admin DM on detection; silent proceed. If already completed, we also stay silent.

                # Execute deposit in a separate background thread so this detector thread can finish quickly
                def _bg_execute_deposit():
                    try:
                        bukmeker = getattr(payment, 'bukmeker', None)
                        player_id = getattr(payment, 'player_id', None)
                        amount = getattr(payment, 'amount', None)
                        user_id = getattr(payment, 'user_id', None)

                        executed = False
                        try:
                            executed = execute_deposit(bukmeker, player_id, amount, {'Success': True})
                        except Exception as e:
                            print(f"Error executing deposit after detection (bg): {e}")

                        if executed:
                            try:
                                bot.send_message(user_id, f"✅ To'lov muvaffaqiyatli amalga oshirildi. Bukmeker: {bukmeker}, Summa: {amount:,.0f} so'm")
                            except Exception:
                                pass

                            # remove keyboard from original payment message if present
                            try:
                                payment_db = db.get_payment_by_id(payment_id)
                                if getattr(payment_db, 'payment_chat_id', None) and getattr(payment_db, 'payment_message_id', None):
                                    try:
                                        chat_id = payment_db.payment_chat_id
                                        # Only edit reply_markup for private chats to avoid touching group/channel messages
                                        if chat_id and int(chat_id) > 0:
                                            bot.edit_message_reply_markup(chat_id, payment_db.payment_message_id, reply_markup=None)
                                    except Exception:
                                        pass
                            except Exception:
                                pass

                            # notify only NOTIFICATION_CHANNEL (no payment group) after successful booking execution
                            try:
                                balance_info = get_balance(bukmeker)
                                user_obj = db.get_user(user_id)
                                channel_message = create_channel_payment_message(
                                    payment_id,
                                    amount,
                                    (user_obj.username if user_obj else "username_yo'q"),
                                    (user_obj.phone if user_obj else "telefon_yo'q"),
                                    balance_info.get('Balance', 0),
                                    balance_info.get('Limit', 0),
                                    bukmeker,
                                    success=True
                                )
                                if getattr(config, 'NOTIFICATION_CHANNEL_ID', None):
                                    bot.send_message(config.NOTIFICATION_CHANNEL_ID, channel_message, parse_mode='HTML')
                            except Exception:
                                pass
                        else:
                            try:
                                db.update_payment_status(payment_id, 'failed')
                            except Exception:
                                pass
                            # No admin spam on failure either
                    except Exception as e:
                        print(f"Unexpected error in background deposit execution: {e}")

                import threading as _threading
                _threading.Thread(target=_bg_execute_deposit, daemon=True).start()

            except Exception as e:
                print(f"Payment detector background error: {e}")

        import threading as _threading
        _threading.Thread(target=_bg_detect_and_handle, args=(parsed, message), daemon=True).start()
    except Exception as e:
        # keep handler silent on errors
        print(f"Payment handler error: {e}")

# Bot holatini tekshirish middleware 
@bot.middleware_handler(update_types=['message'])
def check_bot_status(bot_instance, message):
    # Log incoming messages for debugging (keeps a small trace to inspect button texts)
    try:
        import os
        log_dir = os.path.join(os.getcwd(), 'logs')
        os.makedirs(log_dir, exist_ok=True)
        with open(os.path.join(log_dir, 'incoming_messages.log'), 'a', encoding='utf-8') as f:
            txt = (message.text or '') if hasattr(message, 'text') else ''
            f.write(f"{datetime.now().isoformat()} | {message.from_user.id} | {message.chat.id} | {txt}\n")
    except Exception:
        pass

    if not config.BOT_ACTIVE and message.from_user.id != config.ADMIN_ID:
        try:
            bot.send_message(
                message.chat.id,
                "🚫 Bot texnik ishlar olib borilishi sababli vaqtincha o'chirilgan.\n"
                "Keyinroq urinib ko'ring."
            )
        except Exception:
            pass
        return False

# Noma'lum xabarlar uchun
@bot.message_handler(func=lambda message: True)
def handle_unknown_message(message: Message):
    user_id = message.from_user.id
    
    # Agar foydalanuvchi biror jarayonda bo'lsa, ignore qilamiz
    if is_user_in_process(user_id):
        return
    
    # Admin bo'lsa, admin menyusini ko'rsatish
    if user_id == config.ADMIN_ID:
        bot.send_message(
            user_id,
            "👨‍💼 Admin menyu:",
            reply_markup=get_admin_menu_keyboard()
        )
    else:
        # Oddiy foydalanuvchi uchun
        bot.send_message(
            user_id,
            "❓ Noma'lum buyruq. Quyidagi tugmalardan foydalaning:",
            reply_markup=get_main_menu_keyboard()
        )

# Media xabarlar uchun
@bot.message_handler(func=lambda message: True, content_types=['photo', 'video', 'document', 'audio', 'voice', 'sticker'])
def handle_media_messages(message: Message):
    bot.send_message(
        message.chat.id,
        "❌ Faqat matn xabarlari qabul qilinadi.",
        reply_markup=get_main_menu_keyboard()
    )

if __name__ == "__main__":
    print("🤖 Bot ishga tushdi...")
    print(f"📊 Database: {config.DATABASE_PATH}")
    print(f"👨‍💼 Admin ID: {config.ADMIN_ID}")
    
    try:
        # Database ni tekshirish
        users_count = db.get_users_count()
        print(f"👥 Foydalanuvchilar: {users_count}")
        
        # Polling boshqaruvi - optimallashtirilgan
        import time as _time
        backoff = 1
        while True:
            try:
                # timeout=30 - Telegram API uchun connection timeout
                # long_polling_timeout=25 - Long polling (yangi xabarlarni kutish)
                bot.infinity_polling(
                    timeout=30,
                    long_polling_timeout=25,
                    skip_pending=True  # Eski xabarlarni o'tkazib yuborish
                )
            except KeyboardInterrupt:
                raise
            except Exception as e:
                # Print a concise message and backoff before restarting polling
                print(f"⚠️ Polling error: {e}. Restarting in {backoff}s...")
                import traceback as _tb
                _tb.print_exc()
                _time.sleep(backoff)
                # exponential backoff with cap
                backoff = min(backoff * 2, 60)
                continue
    except KeyboardInterrupt:
        print("\n🛑 Bot to'xtatildi...")
    except Exception as e:
        print(f"❌ Xatolik: {e}")
        import traceback
        traceback.print_exc()
