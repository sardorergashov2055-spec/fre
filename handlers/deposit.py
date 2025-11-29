import telebot
from telebot.types import Message
from database.database import db
from database.models import Payment
from api.xbet_api import xbet_api
from api.mobcash_api import melbet_api, betwiner_api, winwin_api
from api.mostbet_api import mostbet_api
from utils.validators import validate_player_id, validate_amount
from utils.keyboards import get_main_menu_keyboard, get_cancel_keyboard, get_back_keyboard, get_admin_menu_keyboard
import config
from utils.helpers import (generate_payment_id, generate_random_amount, get_random_card, 
                          create_payment_message, create_success_message, create_channel_payment_message)
from utils.state_manager import deposit_states, withdrawal_states, last_menu_action, clear_user_states
from config import MIN_DEPOSIT, MAX_DEPOSIT
import threading
import time

def register_deposit_handlers(bot: telebot.TeleBot):
    
    # Bukmeker tanlash - faqat deposit context da
    @bot.message_handler(func=lambda message: (message.text in ["🎯 1xBet", "🎲 Melbet", "🎰 Mostbet", "🎪 Betwiner", "🎨 WinWinBet"]) and (last_menu_action.get(message.from_user.id) == 'deposit'))
    def select_bukmeker(message: Message):
        user_id = message.from_user.id
        
        # Agar withdrawal_states da mavjud bo'lsa, bu withdrawal
        if user_id in withdrawal_states:
            return
        
        # Foydalanuvchi deposit context da ekanligini tekshirish
        if user_id not in last_menu_action or last_menu_action[user_id] != 'deposit':
            return
        
        bukmeker = message.text.replace("🎯 ", "").replace("🎲 ", "").replace("🎰 ", "").replace("🎪 ", "").replace("🎨 ", "")
        
        deposit_states[user_id] = {
            'action': 'deposit',
            'bukmeker': bukmeker,
            'step': 'player_id'
        }
        
        bot.send_message(
            user_id,
            f"🆔 {bukmeker} ID raqamingizni kiriting:\n\n"
            f"💡 Misol: 123456789",
            reply_markup=get_back_keyboard()
        )
    
    @bot.message_handler(func=lambda message: message.from_user.id in deposit_states and 
                        deposit_states[message.from_user.id].get('action') == 'deposit' and
                        deposit_states[message.from_user.id].get('step') == 'player_id')
    def handle_player_id(message: Message):
        user_id = message.from_user.id
        
        if message.text == "🔙 Orqaga":
            clear_user_states(user_id)
            # Admin uchun orqaga admin paneliga qaytsin
            if user_id == getattr(config, 'ADMIN_ID', None):
                bot.send_message(
                    user_id,
                    "👨‍💼 Admin panel:",
                    reply_markup=get_admin_menu_keyboard()
                )
            else:
                bot.send_message(
                    user_id,
                    "🏠 Asosiy menyu:",
                    reply_markup=get_main_menu_keyboard()
                )
            return
        
        player_id = message.text.strip()

        if not validate_player_id(player_id):
            from utils.bot_helpers import safe_send_message
            safe_send_message(
                bot,
                user_id,
                "❌ Noto'g'ri ID format!\n\n"
                "✅ To'g'ri format:\n"
                "• Kamida 3 ta belgi\n"
                "• Maksimal 20 ta belgi\n"
                "• Faqat raqam va harflar\n\n"
                "Qaytadan kiriting:"
            )
            return

        bukmeker = deposit_states[user_id]['bukmeker']

        # Send immediate acknowledgement so the handler returns quickly
        checking_msg = None
        try:
            from utils.bot_helpers import safe_send_message
            checking_msg = safe_send_message(bot, user_id, "⏳ Tekshirilmoqda...")
        except Exception:
            pass

        # Run player check in background to avoid blocking the telebot worker
        def _async_check_player(u_id: int, bkm: str, p_id: str, check_msg):
            from utils.bot_helpers import safe_send_message
            try:
                player_info = check_player(bkm, p_id)

                # O'chirish yoki yangilash - player topilmasa
                if not player_info.get('Success'):
                    error_msg = player_info.get('error', 'ID topilmadi')
                    try:
                        # Tekshirish xabarini o'chirish
                        if check_msg:
                            try:
                                bot.delete_message(u_id, check_msg.message_id)
                            except Exception:
                                pass
                        
                        safe_send_message(
                            bot,
                            u_id,
                            f"❌ Xatolik yuz berdi!\n\n"
                            f"🔍 Sabab: {error_msg}\n\n"
                            f"💡 Iltimos, ID ni to'g'ri kiriting yoki keyinroq urinib ko'ring.",
                            reply_markup=get_back_keyboard()
                        )
                    except Exception:
                        pass
                    return

                # ID to'g'ri bo'lsa, update state and prompt for amount
                deposit_states[u_id]['player_id'] = p_id
                deposit_states[u_id]['player_info'] = player_info
                deposit_states[u_id]['step'] = 'amount'

                player_name = player_info.get('Name', 'Foydalanuvchi')
                try:
                    # Tekshirish xabarini o'chirish
                    if check_msg:
                        try:
                            bot.delete_message(u_id, check_msg.message_id)
                        except Exception:
                            pass
                    
                    safe_send_message(
                        bot,
                        u_id,
                        f"👤 Foydalanuvchi: {player_name}\n\n"
                        f"💰 To'lash summasini kiriting:\n\n"
                        f"💡 Minimal: {MIN_DEPOSIT:,} so'm\n"
                        f"💡 Maksimal: {MAX_DEPOSIT:,} so'm\n\n"
                        f"📝 Misol: 50000",
                        reply_markup=get_back_keyboard()
                    )
                except Exception:
                    pass
            except Exception:
                try:
                    # Tekshirish xabarini o'chirish
                    if check_msg:
                        try:
                            bot.delete_message(u_id, check_msg.message_id)
                        except Exception:
                            pass
                    
                    safe_send_message(bot, u_id, "❌ Xatolik yuz berdi. Iltimos keyinroq urinib ko'ring.")
                except Exception:
                    pass

        threading.Thread(target=_async_check_player, args=(user_id, bukmeker, player_id, checking_msg), daemon=True).start()
    
    @bot.message_handler(func=lambda message: message.from_user.id in deposit_states and 
                        deposit_states[message.from_user.id].get('action') == 'deposit' and
                        deposit_states[message.from_user.id].get('step') == 'amount')
    def handle_amount(message: Message):
        from utils.bot_helpers import safe_send_message
        user_id = message.from_user.id
        
        if message.text == "🔙 Orqaga":
            deposit_states[user_id]['step'] = 'player_id'
            bukmeker = deposit_states[user_id]['bukmeker']
            safe_send_message(
                bot,
                user_id,
                f"🆔 {bukmeker} ID raqamingizni kiriting:\n\n"
                f"💡 Misol: 123456789",
                reply_markup=get_back_keyboard()
            )
            return
        
        amount_text = message.text.strip()
        
        is_valid, amount = validate_amount(amount_text, MIN_DEPOSIT, MAX_DEPOSIT)
        
        if not is_valid:
            safe_send_message(
                bot,
                user_id,
                f"❌ Noto'g'ri summa!\n\n"
                f"💡 Minimal: {MIN_DEPOSIT:,} so'm\n"
                f"💡 Maksimal: {MAX_DEPOSIT:,} so'm\n\n"
                f"📝 Faqat raqam kiriting. Misol: 50000\n\n"
                "Qaytadan kiriting:"
            )
            return
        
        state = deposit_states[user_id]
        bukmeker = state['bukmeker']
        player_id = state['player_id']
        player_info = state.get('player_info', {'Success': True})
        
        # To'lov jarayonini boshlash - DARHOL xabar yuborish
        from utils.bot_helpers import safe_send_message
        opening_msg = safe_send_message(bot, user_id, "⏳ To'lov oynasi ochilmoqda...")
        
        # Agar xabar yuborilmasa, qayta urinish
        if not opening_msg:
            # Retry bir marta
            import time
            time.sleep(0.5)
            opening_msg = safe_send_message(bot, user_id, "⏳ To'lov oynasi ochilmoqda...")
        
        process_deposit(bot, user_id, bukmeker, player_id, amount, player_info, opening_msg)
        
        # State ni tozalash
        clear_user_states(user_id)

def check_player(bukmeker: str, player_id: str) -> dict:
    """Player ni tekshirish"""
    try:
        if bukmeker == "1xBet":
            if xbet_api:
                result = xbet_api.find_player(player_id)
                # API xatolik qaytarsa ham, Success True bo'lsa
                if result.get('Success'):
                    return result
                else:
                    return {'Success': False, 'error': result.get('error', 'API xatolik')}
            else:
                # API mavjud bo'lmasa, player mavjud deb qabul qilamiz
                return {'Success': True, 'UserId': player_id, 'Name': 'Player'}
                
        elif bukmeker == "Melbet":
            if melbet_api:
                result = melbet_api.find_player(player_id)
                if result.get('Success'):
                    return result
                else:
                    return {'Success': False, 'error': result.get('error', 'API xatolik')}
            else:
                return {'Success': True, 'UserId': player_id, 'Name': 'Player'}
                
        elif bukmeker == "Betwiner":
            if betwiner_api:
                result = betwiner_api.find_player(player_id)
                if result.get('Success'):
                    return result
                else:
                    return {'Success': False, 'error': result.get('error', 'API xatolik')}
            else:
                return {'Success': True, 'UserId': player_id, 'Name': 'Player'}
                
        elif bukmeker == "WinWinBet":
            if winwin_api:
                result = winwin_api.find_player(player_id)
                if result.get('Success'):
                    return result
                else:
                    return {'Success': False, 'error': result.get('error', 'API xatolik')}
            else:
                return {'Success': True, 'UserId': player_id, 'Name': 'Player'}
                
        elif bukmeker == "Mostbet":
            if mostbet_api:
                result = mostbet_api.find_player(player_id)
                if result.get('Success'):
                    return result
                else:
                    return {'Success': False, 'error': result.get('error', 'API xatolik')}
            else:
                return {'Success': True, 'UserId': player_id, 'Name': 'Player'}
        else:
            return {'Success': False, 'error': 'Noma\'lum bukmeker'}
            
    except Exception as e:
        # API xatolik bo'lsa ham davom ettiramiz
        return {'Success': True, 'UserId': player_id, 'Name': 'Player', 'warning': 'API not available'}

def process_deposit(bot: telebot.TeleBot, user_id: int, bukmeker: str, 
                   player_id: str, amount: float, player_info: dict, opening_msg=None):
    """To'lov jarayonini boshqarish"""
    from utils.bot_helpers import safe_send_message, safe_edit_text
    
    try:
        # Random qo'shimcha summa
        random_addition = generate_random_amount()
        final_amount = amount + random_addition
        
        # Random karta tanlash
        cards = db.get_active_cards()
        
        if not cards:
            safe_send_message(
                bot,
                user_id,
                "❌ Hozirda to'lov kartalari yangilanmoqta. Keyinroq urinib ko'ring.",
                reply_markup=get_main_menu_keyboard()
            )
            return
        
        card = get_random_card(cards)
        payment_id = generate_payment_id()
        
        # To'lovni bazaga saqlash
        payment = Payment(
            user_id=user_id,
            bukmeker=bukmeker,
            player_id=player_id,
            amount=final_amount,
            payment_id=payment_id,
            card_last4=card.card_number[-4:]
        )
        
        if not db.add_payment(payment):
            safe_send_message(
                bot,
                user_id,
                "❌ Xatolik yuz berdi. Qaytadan urinib ko'ring.",
                reply_markup=get_main_menu_keyboard()
            )
            return
        
        # To'lov oynasini yuborish
        payment_message = create_payment_message(
            bukmeker, player_id, card.card_number, 
            final_amount, amount, payment_id, user_id
        )
        
        sent_msg = None
        if opening_msg:
            try:
                bot.delete_message(user_id, opening_msg.message_id)
            except Exception:
                pass
        
        sent_msg = safe_send_message(
            bot,
            user_id,
            payment_message,
            parse_mode='HTML',
            reply_markup=get_cancel_keyboard(),
        )

        # store message ids so we can edit/remove keyboard later on success/failure
        try:
            if sent_msg and hasattr(sent_msg, 'chat') and hasattr(sent_msg, 'message_id'):
                db.update_payment_message_ids(payment_id, sent_msg.chat.id, sent_msg.message_id)
        except Exception:
            pass
        
        # To'lov guruhdan PAYMENT xabari kelishini kutamiz
        # monitor_payment o'chirildi - faqat guruh PAYMENT xabari orqali tasdiqlash
        
    except Exception as e:
        # Xato holatida safe wrapper bilan xabar yuborish
        from utils.bot_helpers import safe_send_message
        if user_id == getattr(config, 'ADMIN_ID', None):
            safe_send_message(
                bot,
                user_id,
                "❌ Xatolik yuz berdi. Qaytadan urinib ko'ring.",
                reply_markup=get_admin_menu_keyboard()
            )
        else:
            safe_send_message(
                bot,
                user_id,
                "❌ Xatolik yuz berdi. Qaytadan urinib ko'ring.",
                reply_markup=get_main_menu_keyboard()
            )

def get_balance(bukmeker: str, player_id: str = None) -> dict:
    """Balansni olish - player_id ixtiyoriy"""
    try:
        if bukmeker == "1xBet":
            if xbet_api:
                return xbet_api.get_balance()
            return {'Success': False, 'Balance': 0, 'Limit': 0}
            
        elif bukmeker == "Melbet":
            if melbet_api:
                return melbet_api.get_balance()
            return {'Success': False, 'Balance': 0, 'Limit': 0}
            
        elif bukmeker == "Betwiner":
            if betwiner_api:
                return betwiner_api.get_balance()
            return {'Success': False, 'Balance': 0, 'Limit': 0}
            
        elif bukmeker == "WinWinBet":
            if winwin_api:
                return winwin_api.get_balance()
            return {'Success': False, 'Balance': 0, 'Limit': 0}
            
        elif bukmeker == "Mostbet":
            if mostbet_api:
                return mostbet_api.get_balance()
            return {'Success': False, 'Balance': 0, 'Limit': 0}
        else:
            return {'Success': False, 'Balance': 0, 'Limit': 0}
            
    except Exception as e:
        return {'Success': False, 'Balance': 0, 'Limit': 0}

def monitor_payment(bot: telebot.TeleBot, user_id: int, payment_id: str, 
                   bukmeker: str, player_id: str, final_amount: float, player_info: dict):
    """To'lovni kuzatish"""
    from utils.bot_helpers import safe_send_message
    
    try:
        time.sleep(300)  # 5 daqiqa kutish
        
        payment = db.get_payment_by_id(payment_id)
        if not payment or payment.status != 'pending':
            return
        
        # To'lovni amalga oshirish
        # Execute using the exact required final amount (original amount + random add-on)
        success = execute_deposit(bukmeker, player_id, final_amount, player_info)
        
        if success:
            db.update_payment_status(payment_id, 'completed')
            success_message = create_success_message(bukmeker, player_id, final_amount)
            safe_send_message(
                bot,
                user_id,
                success_message,
                reply_markup=get_main_menu_keyboard()
            )
            # remove keyboard from original payment message if present
            try:
                payment = db.get_payment_by_id(payment_id)
                if getattr(payment, 'payment_chat_id', None) and getattr(payment, 'payment_message_id', None):
                    try:
                        chat_id = payment.payment_chat_id
                        # Only edit reply_markup for private chats to avoid touching group/channel messages
                        if chat_id and int(chat_id) > 0:
                            bot.edit_message_reply_markup(chat_id, payment.payment_message_id, reply_markup=None)
                    except Exception:
                        pass
                # notify payment channel about success
                # Only post to NOTIFICATION_CHANNEL_ID (payment channel disabled per new policy)
                try:
                    from config import NOTIFICATION_CHANNEL_ID
                except Exception:
                    NOTIFICATION_CHANNEL_ID = None
                if NOTIFICATION_CHANNEL_ID:
                    try:
                        user_obj = db.get_user(user_id)
                        channel_message = create_channel_payment_message(
                            payment_id, final_amount, (user_obj.username if user_obj else "username_yo'q"),
                            (user_obj.phone if user_obj else "telefon_yo'q"),
                            0, 0, bukmeker, success=True
                        )
                        safe_send_message(bot, NOTIFICATION_CHANNEL_ID, channel_message, parse_mode='HTML')
                    except Exception:
                        pass
            except Exception:
                pass
        else:
            db.update_payment_status(payment_id, 'failed')
            safe_send_message(
                bot,
                user_id,
                "❌ To'lov vaqti tugadi qayta urunib ko'ring /start.",
                reply_markup=get_main_menu_keyboard()
            )
            # if failed, also remove keyboard to avoid confusion
            try:
                payment = db.get_payment_by_id(payment_id)
                if getattr(payment, 'payment_chat_id', None) and getattr(payment, 'payment_message_id', None):
                    try:
                        chat_id = payment.payment_chat_id
                        # Only edit reply_markup for private chats to avoid touching group/channel messages
                        if chat_id and int(chat_id) > 0:
                            bot.edit_message_reply_markup(chat_id, payment.payment_message_id, reply_markup=None)
                    except Exception:
                        pass
            except Exception:
                pass
    except Exception as e:
        pass

def execute_deposit(bukmeker: str, player_id: str, amount: float, player_info: dict) -> bool:
    """To'lovni amalga oshirish"""
    try:
        if bukmeker == "1xBet":
            if xbet_api:
                result = xbet_api.deposit_add(player_id, amount)
                return result.get('Success', False)
            return False
            
        elif bukmeker == "Melbet":
            if melbet_api:
                result = melbet_api.deposit_add(player_id, amount)
                return result.get('Success', False)
            return False
            
        elif bukmeker == "Betwiner":
            if betwiner_api:
                result = betwiner_api.deposit_add(player_id, amount)
                return result.get('Success', False)
            return False
            
        elif bukmeker == "WinWinBet":
            if winwin_api:
                result = winwin_api.deposit_add(player_id, amount)
                return result.get('Success', False)
            return False
            
        elif bukmeker == "Mostbet":
            if mostbet_api:
                result = mostbet_api.deposit_player(1, player_id, amount)
                # Mostbet API Success False qaytaradi muvaffaqiyatli bo'lsa
                return not result.get('Success', True)
            return False
        else:
            return False
            
    except Exception:
        return False


def execute_deposit_detailed(bukmeker: str, player_id: str, amount: float, player_info: dict) -> dict:
    """Depositni API orqali sinab ko'radi va to'liq natijani qaytaradi (admin uchun).

    Returns a dict with at least 'Success': bool and optional 'Error'/'Message'.
    """
    try:
        if bukmeker == "1xBet":
            if xbet_api:
                return xbet_api.deposit_add(player_id, amount)
            return {'Success': False, 'Error': '1xBet API mavjud emas'}

        elif bukmeker == "Melbet":
            if melbet_api:
                return melbet_api.deposit_add(player_id, amount)
            return {'Success': False, 'Error': 'Melbet API mavjud emas'}

        elif bukmeker == "Betwiner":
            if betwiner_api:
                return betwiner_api.deposit_add(player_id, amount)
            return {'Success': False, 'Error': 'Betwiner API mavjud emas'}

        elif bukmeker == "WinWinBet":
            if winwin_api:
                return winwin_api.deposit_add(player_id, amount)
            return {'Success': False, 'Error': 'WinWinBet API mavjud emas'}

        elif bukmeker == "Mostbet":
            if mostbet_api:
                return mostbet_api.deposit_player(1, player_id, amount)
            return {'Success': False, 'Error': 'Mostbet API mavjud emas'}
        else:
            return {'Success': False, 'Error': 'Noma\'lum bukmeker'}

    except Exception as e:
        return {'Success': False, 'Error': str(e)}

# Bekor qilish callback
def register_cancel_callback(bot: telebot.TeleBot):
    @bot.callback_query_handler(func=lambda call: call.data == "cancel_payment")
    def cancel_payment_callback(call):
        user_id = call.from_user.id
        clear_user_states(user_id)
        
        try:
            bot.edit_message_text(
                "To'lovni bekor qildingiz.",
                "Qayta urunib ko'ring /start",
                call.message.chat.id,
                call.message.message_id
            )
        except:
            pass
        
        bot.send_message(
            user_id,
            "🏠 Asosiy menyu.Buyruqni tanlang:",
            reply_markup=get_main_menu_keyboard()
        )
