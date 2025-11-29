import telebot
from telebot.types import CallbackQuery
from database.database import db
from utils.keyboards import get_main_menu_keyboard

def register_payment_handlers(bot: telebot.TeleBot):
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith("approve_withdrawal_"))
    def approve_withdrawal(call: CallbackQuery):
        """Pul yechishni tasdiqlash"""
        try:
            withdrawal_id = int(call.data.replace("approve_withdrawal_", ""))
            
            # Withdrawal holatini yangilash
            if db.update_withdrawal_status(withdrawal_id, "approved"):
                bot.edit_message_text(
                    "✅ Pul yechish tasdiqlandi!",
                    call.message.chat.id,
                    call.message.message_id
                )
            else:
                bot.answer_callback_query(call.id, "❌ Xatolik yuz berdi!")
                
        except Exception as e:
            bot.answer_callback_query(call.id, f"❌ Xatolik: {str(e)}")
    # cancel_payment callback handler moved to handlers/deposit.register_cancel_callback
    # to avoid duplicate handlers and keep logic in one place.
