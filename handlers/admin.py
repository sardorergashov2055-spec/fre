import telebot
from telebot.types import Message, CallbackQuery
from database.database import db
from database.models import Card
from utils.keyboards import (get_admin_menu_keyboard, get_main_menu_keyboard_admin,
                           get_card_management_keyboard, get_balance_keyboard, get_back_keyboard,
                           get_bookmakers_keyboard, get_admin_manual_deposit_confirm_keyboard)
from utils.helpers import create_balance_message, create_stats_message, log_manual_deposit
from utils.bot_helpers import safe_send_message  # resilient send wrapper
from utils.validators import validate_card_number, validate_amount, validate_player_id
from api.xbet_api import xbet_api
from api.mobcash_api import melbet_api, betwiner_api, winwin_api
from concurrent.futures import ThreadPoolExecutor, wait
from threading import Thread
import time
from handlers.deposit import execute_deposit_detailed
from handlers.deposit import check_player
from config import ADMIN_ID
import config

admin_states = {}

def register_admin_handlers(bot: telebot.TeleBot):
    
    # Admin panel tugmasi
    @bot.message_handler(func=lambda message: message.from_user.id == ADMIN_ID and message.text == "👨‍💼 Admin panel")
    def admin_panel(message: Message):
        bot.send_message(
            ADMIN_ID,
            "👨‍💼 Admin panel:",
            reply_markup=get_admin_menu_keyboard()
        )
    
    # Admin menyu komandasi
    @bot.message_handler(func=lambda message: message.from_user.id == ADMIN_ID and message.text == "👤 Foydalanuvchi menyu")
    def user_menu(message: Message):
        bot.send_message(
            message.chat.id,
            "👤 Foydalanuvchi menyusi:",
            reply_markup=get_main_menu_keyboard_admin()
        )
    
    # Qo'lda to'ldirish
    @bot.message_handler(func=lambda message: message.from_user.id == ADMIN_ID and message.text == "✋ Qo'lda to'ldirish")
    def manual_deposit(message: Message):
        admin_states[ADMIN_ID] = {'action': 'manual_deposit', 'step': 'bukmeker'}
        
        bot.send_message(
            ADMIN_ID,
            "Bukmekerlardan birini tanlang:",
            reply_markup=get_bookmakers_keyboard()
        )
    
    # Statistika
    @bot.message_handler(func=lambda message: message.from_user.id == ADMIN_ID and message.text == "📊 Statistika")
    def show_stats(message: Message):
        users_count = db.get_users_count()
        stats_message = create_stats_message(users_count, 0, 0)  # TODO: implement daily stats
        
        bot.send_message(ADMIN_ID, stats_message)
    
    # Xabar yuborish
    @bot.message_handler(func=lambda message: message.from_user.id == ADMIN_ID and message.text == "📢 Xabar yuborish")
    def broadcast_message(message: Message):
        admin_states[ADMIN_ID] = {'action': 'broadcast'}
        
        bot.send_message(
            ADMIN_ID,
            "📢 Xabar yuboring: matn yozing yoki rasm/video yuboring",
            reply_markup=get_back_keyboard()
        )
    
    # Bot o'chirish/yoqish
    @bot.message_handler(func=lambda message: message.from_user.id == ADMIN_ID and message.text == "🔧 Bot o'chirish")
    def toggle_bot(message: Message):
        config.BOT_ACTIVE = not config.BOT_ACTIVE
        status = "✅ yoqildi" if config.BOT_ACTIVE else "❌ o'chirildi"
        
        bot.send_message(ADMIN_ID, f"🔧 Bot {status}")
    
    # Karta boshqaruvi
    @bot.message_handler(func=lambda message: message.from_user.id == ADMIN_ID and message.text == "💳 Karta qo'shish")
    def card_management(message: Message):
        bot.send_message(
            ADMIN_ID,
            "💳 Karta boshqaruvi:",
            reply_markup=get_card_management_keyboard()
        )
    
    # Balans ko'rish
    @bot.message_handler(func=lambda message: message.from_user.id == ADMIN_ID and message.text == "💰 Kasa balansi")
    def show_balance(message: Message):
        # Simple in-memory cache to avoid repeated slow balance fetches
        # Cache key is static (admin view). TTL controlled by config.BALANCE_CACHE_SECONDS
        cache_key = 'admin_balances'
        now = time.time()
        try:
            last = getattr(register_admin_handlers, '_last_balances_ts', 0)
            cached = getattr(register_admin_handlers, '_last_balances', None)
        except Exception:
            last = 0
            cached = None

        if cached and (now - last) < getattr(config, 'BALANCE_CACHE_SECONDS', 5):
            # Serve cached immediately
            try:
                bot.send_message(ADMIN_ID, cached, reply_markup=get_balance_keyboard())
                return
            except Exception:
                # if sending cached fails, proceed to fresh fetch
                pass

        # Fetch balances concurrently for speed and robustness, but don't block the bot worker.
        providers = {
            '1xBet': lambda: xbet_api.get_balance() if xbet_api else {'Success': False},
            'Melbet': lambda: melbet_api.get_balance() if melbet_api else {'Success': False},
            'Betwiner': lambda: betwiner_api.get_balance() if betwiner_api else {'Success': False},
            'WinWinBet': lambda: winwin_api.get_balance() if winwin_api else {'Success': False},
        }

        def fetch_and_update(message_id: int):
            balances = {}
            with ThreadPoolExecutor(max_workers=4) as ex:
                future_map = {ex.submit(func): name for name, func in providers.items()}
                try:
                    # 10 soniya timeout - barcha API chaqiruvlari uchun yetarli
                    done, not_done = wait(future_map.keys(), timeout=10)
                except Exception:
                    done = set()
                    not_done = set(future_map.keys())

                for fut in done:
                    name = future_map.get(fut)
                    try:
                        res = fut.result(timeout=0.5)
                    except Exception as e:
                        res = {'Success': False, 'Error': 'Server javob bermadi'}
                    balances[name] = res

                for fut in not_done:
                    name = future_map.get(fut)
                    try:
                        fut.cancel()
                    except Exception:
                        pass
                    balances[name] = {'Success': False, 'Error': 'Server javob bermadi'}
            # (logging removed for performance)

            balance_message = create_balance_message(balances)
            # cache the rendered message
            try:
                register_admin_handlers._last_balances = balance_message
                register_admin_handlers._last_balances_ts = time.time()
            except Exception:
                pass
            # Always send the final balance message (editing can sometimes silently fail
            # due to message id mismatches). After sending, try to remove the loading message
            # to keep chat tidy.
            try:
                bot.send_message(ADMIN_ID, balance_message, reply_markup=get_balance_keyboard())
            except Exception:
                pass  # (logging removed)

            # Try to remove the loading message if we have its id
            if message_id:
                try:
                    try:
                        bot.delete_message(ADMIN_ID, message_id)
                    except Exception:
                        # best-effort - ignore failures
                        pass
                except Exception:
                    pass

        # Send immediate acknowledgement so buttons stay responsive
        try:
            status_msg = bot.send_message(ADMIN_ID, "🔄 Balans olinmoqda... Iltimos kuting.", reply_markup=get_balance_keyboard())
            # Run the slow work in a daemon thread so the handler returns immediately
            t = Thread(target=fetch_and_update, args=(status_msg.message_id,), daemon=True)
            t.start()
        except Exception:
            # If sending the status message fails, fall back to synchronous behaviour but still protect the handler
            # (this is a last resort; should be rare)
            fetch_and_update(None)
    
    # Balans yangilash
    @bot.message_handler(func=lambda message: message.from_user.id == ADMIN_ID and message.text == "🔄 Yangilash")
    def refresh_balance(message: Message):
        # Cache'ni tozalash - yangi balans olinadi
        try:
            register_admin_handlers._last_balances_ts = 0
        except Exception:
            pass
        
        # Fetch balances
        providers = {
            '1xBet': lambda: xbet_api.get_balance() if xbet_api else {'Success': False},
            'Melbet': lambda: melbet_api.get_balance() if melbet_api else {'Success': False},
            'Betwiner': lambda: betwiner_api.get_balance() if betwiner_api else {'Success': False},
            'WinWinBet': lambda: winwin_api.get_balance() if winwin_api else {'Success': False},
        }

        def fetch_and_send():
            balances = {}
            with ThreadPoolExecutor(max_workers=4) as ex:
                future_map = {ex.submit(func): name for name, func in providers.items()}
                try:
                    done, not_done = wait(future_map.keys(), timeout=10)
                except Exception:
                    done = set()
                    not_done = set(future_map.keys())

                for fut in done:
                    name = future_map.get(fut)
                    try:
                        res = fut.result(timeout=0.5)
                    except Exception as e:
                        res = {'Success': False, 'Error': 'Server javob bermadi'}
                    balances[name] = res

                for fut in not_done:
                    name = future_map.get(fut)
                    try:
                        fut.cancel()
                    except Exception:
                        pass
                    balances[name] = {'Success': False, 'Error': 'Server javob bermadi'}

            balance_message = create_balance_message(balances)
            # Cache yangilash
            try:
                register_admin_handlers._last_balances = balance_message
                register_admin_handlers._last_balances_ts = time.time()
            except Exception:
                pass
            
            try:
                bot.send_message(ADMIN_ID, balance_message, reply_markup=get_balance_keyboard())
            except Exception:
                pass

        # Background thread
        Thread(target=fetch_and_send, daemon=True).start()
        try:
            bot.send_message(ADMIN_ID, "🔄 Yangilanmoqda...", reply_markup=get_balance_keyboard())
        except Exception:
            pass
    
    # Admin state handler - TEXT
    @bot.message_handler(func=lambda message: message.from_user.id == ADMIN_ID and ADMIN_ID in admin_states, content_types=['text'])
    def handle_admin_states(message: Message):
        # Agar admin menyu tugmalari bosilsa, state'ni bekor qilib, tegishli handlerga yo'naltirish
        # MUHIM: Qo'lda to'ldirish bosqichida bukmeker tanlash uchun bu tugmalar state'ni o'chirmasligi kerak
        menu_buttons = [
            "👨‍💼 Admin panel", "👤 Foydalanuvchi menyu", "✋ Qo'lda to'ldirish",
            "📊 Statistika", "📢 Xabar yuborish", "🔧 Bot o'chirish",
            "💳 Karta qo'shish", "💰 Kasa balansi", "🔄 Yangilash",
            "➕ Karta qo'shish", "📋 Kartalar ro'yxati", "❌ Karta o'chirish"
        ]
        
        if message.text in menu_buttons:
            # State'ni tozalash va boshqa handlerga imkon berish
            if ADMIN_ID in admin_states:
                del admin_states[ADMIN_ID]
            # Handler qaytadi va keyingi handler ishlaydi
            return
        
        state = admin_states.get(ADMIN_ID)
        if not state:
            return
        action = state.get('action')
        if action == 'manual_deposit':
            handle_manual_deposit(bot, message)
        elif action == 'add_card':
            handle_add_card(bot, message)
        elif action == 'delete_card':
            handle_delete_card(bot, message)
        elif action == 'broadcast':
            handle_broadcast(bot, message)
        else:
            bot.send_message(ADMIN_ID, "❌ Ushbu amal hozircha qo'llab-quvvatlanmaydi.")

    # Admin state handler - MEDIA (broadcast endi photo/video qabul qiladi)
    @bot.message_handler(func=lambda message: message.from_user.id == ADMIN_ID and ADMIN_ID in admin_states, content_types=['photo', 'video', 'document', 'animation'])
    def handle_admin_states_media(message: Message):
        state = admin_states.get(ADMIN_ID)
        if not state:
            return
        action = state.get('action')
        if action == 'broadcast':
            handle_broadcast(bot, message)
        else:
            bot.send_message(ADMIN_ID, "❌ Faqat matn xabarlari qabul qilinadi.")
    
    # Karta qo'shish
    @bot.message_handler(func=lambda message: message.from_user.id == ADMIN_ID and message.text == "➕ Karta qo'shish")
    def add_card_start(message: Message):
        admin_states[ADMIN_ID] = {'action': 'add_card', 'step': 'card_number'}
        
        bot.send_message(
            ADMIN_ID,
            "💳 Karta raqamini kiriting (16 ta raqam):",
            reply_markup=get_back_keyboard()
        )
    
    # Kartalar ro'yxati
    @bot.message_handler(func=lambda message: message.from_user.id == ADMIN_ID and message.text == "📋 Kartalar ro'yxati")
    def list_cards(message: Message):
        cards = db.get_active_cards()
        
        if cards:
            message_text = "💳 Aktiv kartalar:\n\n"
            for i, card in enumerate(cards, 1):
                last4 = card.card_number[-4:]
                message_text += f"{i}. ****{last4}\n"
        else:
            message_text = "❌ Aktiv kartalar yo'q"
        
        bot.send_message(ADMIN_ID, message_text)
    
    # Karta o'chirish
    @bot.message_handler(func=lambda message: message.from_user.id == ADMIN_ID and message.text == "❌ Karta o'chirish")
    def delete_card_start(message: Message):
        admin_states[ADMIN_ID] = {'action': 'delete_card'}
        
        cards = db.get_active_cards()
        if cards:
            message_text = "❌ O'chirish uchun karta raqamini kiriting:\n\n"
            for i, card in enumerate(cards, 1):
                last4 = card.card_number[-4:]
                message_text += f"{i}. {card.card_number} (****{last4})\n"
            
            bot.send_message(ADMIN_ID, message_text, reply_markup=get_back_keyboard())
        else:
            bot.send_message(ADMIN_ID, "❌ O'chirish uchun kartalar yo'q")

    # Admin manual deposit callback handler
    @bot.callback_query_handler(func=lambda call: call.data in ['admin_md_confirm','admin_md_cancel'])
    def admin_manual_deposit_callback(call: CallbackQuery):
        # State check - yanada yumshoq
        state = admin_states.get(ADMIN_ID)
        if not state:
            try:
                bot.answer_callback_query(call.id, "⏳ Qayta urinib ko'ring")
            except Exception:
                pass
            return
            
        data = call.data
        if data == 'admin_md_cancel':
            # Bekor qilish - oynani o'chirish
            bukmeker = state.get('bukmeker', '—')
            player_id = state.get('player_id', '—')
            amount = state.get('amount', 0)
            
            # Avvalgi oynani o'chirish
            try:
                bot.delete_message(ADMIN_ID, call.message.message_id)
            except Exception:
                pass
            
            # Bekor qilindi xabari
            cancel_msg = (
                f"❌ Bekor qilindi\n\n"
                f"Bukmeker: {bukmeker}\n"
                f"ID: {player_id}\n"
                f"Summa: {amount:,.0f} so'm"
            )
            
            safe_send_message(bot, ADMIN_ID, cancel_msg)
            
            try:
                del admin_states[ADMIN_ID]
            except Exception:
                pass
            
            safe_send_message(bot, ADMIN_ID, "👨‍💼 Admin panel:", reply_markup=get_admin_menu_keyboard())
            return
            
        # Tasdiqlash - state'dan ma'lumot olish
        bukmeker = state.get('bukmeker')
        player_id = state.get('player_id')
        amount = state.get('amount')
        player_info = state.get('player_info', {})
        
        if not all([bukmeker, player_id, amount]):
            try:
                bot.answer_callback_query(call.id, "❌ Ma'lumot yetarli emas")
            except Exception:
                pass
            return
            
        try:
            bot.answer_callback_query(call.id, "⏳ Ishlanmoqda...")
        except Exception:
            pass
        
        # DARHOL deposit - background emas!
        result = None
        try:
            result = execute_deposit_detailed(bukmeker, player_id, amount, player_info)
        except Exception as e:
            result = {'Success': False, 'Error': str(e)}
        
        # Log
        try:
            log_manual_deposit({'bukmeker': bukmeker, 'player_id': player_id, 'amount': amount, 'result': result})
        except Exception:
            pass
        
        succ = result.get('Success')
        if succ:
            # Balans olish - to'g'ri funksiya
            balance_info = {'Balance': 0, 'Limit': 0}
            try:
                from handlers.deposit import get_balance
                balance_result = get_balance(bukmeker, player_id)
                if balance_result and balance_result.get('Success'):
                    balance_info['Balance'] = balance_result.get('Balance', 0)
                    balance_info['Limit'] = balance_result.get('Limit', 0)
            except Exception:
                pass
            
            # Admin'ga muvaffaqiyatli xabar - to'lov oynasini yopish
            player_name = player_info.get('Name') or player_info.get('name') or '—'
            
            # Avvalgi to'ldirish oynasini o'chirish
            try:
                bot.delete_message(ADMIN_ID, call.message.message_id)
            except Exception:
                pass
            
            # Yangi muvaffaqiyatli xabar yuborish
            success_msg = (
                "✅ Operatsiya muvaffaqiyatli o'tdi!\n\n"
                f"Bukmeker: {bukmeker}\n"
                f"ID: {player_id}\n"
                f"Summa: {amount:,.0f} so'm\n"
                f"To'lov tizimi komissiyasi: 0%\n\n"
                f"Kassa holati:\n"
                f"  Balans: {balance_info['Balance']:,.0f} so'm\n"
                f"  Limit: {balance_info['Limit']:,.0f} so'm"
            )
            
            safe_send_message(bot, ADMIN_ID, success_msg)
            
            # KANAL XABARI - QO'LDA TO'LDIRISH (sodda format)
            try:
                if getattr(config, 'NOTIFICATION_CHANNEL_ID', None):
                    channel_msg = (
                        f"✅ Operatsiya muvaffaqiyatli o'tdi!\n\n"
                        f"Bukmeker: {bukmeker}\n"
                        f"ID: {player_id}\n"
                        f"Summa: {amount:,.0f} so'm\n\n"
                        f"Kassa:\n"
                        f"  Balans: {balance_info['Balance']:,.0f} so'm\n"
                        f"  Limit: {balance_info['Limit']:,.0f} so'm\n\n"
                        f"(Qo'lda to'ldirildi)"
                    )
                    safe_send_message(
                        bot,
                        config.NOTIFICATION_CHANNEL_ID,
                        channel_msg
                    )
            except Exception as e:
                # Xatoni log qilish
                try:
                    print(f"[ADMIN] Kanal xabari yuborishda xato: {e}")
                except Exception:
                    pass
        else:
            # Muvaffaqiyatsiz - oynani o'chirish va xabar yuborish
            err = result.get('Error') or result.get('error') or result.get('Message') or 'Noma\'lum xatolik'
            
            # Avvalgi oynani o'chirish
            try:
                bot.delete_message(ADMIN_ID, call.message.message_id)
            except Exception:
                pass
            
            error_msg = (
                f"❌ To'lov muvaffaqiyatsiz!\n\n"
                f"Bukmeker: {bukmeker}\n"
                f"ID: {player_id}\n"
                f"Summa: {amount:,.0f} so'm\n\n"
                f"Sabab: {err}"
            )
            
            safe_send_message(bot, ADMIN_ID, error_msg)
        
        # State tozalash
        try:
            del admin_states[ADMIN_ID]
        except Exception:
            pass
        
        # Admin panel qaytarish
        safe_send_message(bot, ADMIN_ID, "👨‍💼 Admin panel:", reply_markup=get_admin_menu_keyboard())

def handle_manual_deposit(bot: telebot.TeleBot, message: Message):
    """Qo'lda to'ldirish (tasdiqlash bosqichi bilan)"""
    state = admin_states.get(ADMIN_ID)
    if not state:
        return
    step = state.get('step')

    # Orqaga
    if message.text == "🔙 Orqaga":
        del admin_states[ADMIN_ID]
        safe_send_message(bot, ADMIN_ID, "👨‍💼 Admin panel:", reply_markup=get_admin_menu_keyboard())
        return

    if step == 'bukmeker':
        valid = {"🎯 1xBet": "1xBet", "🎲 Melbet": "Melbet", "🎪 Betwiner": "Betwiner", "🎨 WinWinBet": "WinWinBet", "1xBet": "1xBet", "Melbet": "Melbet", "Betwiner": "Betwiner", "WinWinBet": "WinWinBet"}
        chosen = valid.get(message.text)
        if not chosen:
            # Debug: konsolga xabar chiqarish
            try:
                print(f"[DEBUG] Noto'g'ri bukmeker tanlovi: '{message.text}'")
            except Exception:
                pass
            safe_send_message(bot, ADMIN_ID, "❌ Noto'g'ri tanlov! Tugmadan foydalaning:")
            return
        state['bukmeker'] = chosen
        state['step'] = 'player_id'
        safe_send_message(bot, ADMIN_ID, f"🆔 {chosen} ID raqamini kiriting:", reply_markup=get_back_keyboard())

    elif step == 'player_id':
        player_id = (message.text or '').strip()
        if not validate_player_id(player_id):
            safe_send_message(bot, ADMIN_ID, "❌ Noto'g'ri ID format! Qaytadan kiriting:")
            return
        bukmeker = state['bukmeker']
        player_info = check_player(bukmeker, player_id)
        if not player_info.get('Success'):
            error_msg = player_info.get('Error') or player_info.get('Message') or 'Topilmadi'
            safe_send_message(bot, ADMIN_ID, f"❌ {bukmeker} da bunday ID topilmadi!\nXato: {error_msg}\n\nQaytadan kiriting:")
            return
        state['player_id'] = player_id
        state['player_info'] = player_info
        state['step'] = 'amount'
        player_name = player_info.get('Name') or player_info.get('name') or ''
        suffix = f" (👤 {player_name})" if player_name else ''
        # Use safe_send_message with retries to avoid ConnectionResetError (WinError 10054) crashing the polling thread
        safe_send_message(bot, ADMIN_ID, f"💰 Summani kiriting (so'm){suffix}:", reply_markup=get_back_keyboard())

    elif step == 'amount':
        is_valid, amount = validate_amount(message.text, 1000, 50000000)
        if not is_valid:
            safe_send_message(bot, ADMIN_ID, "❌ Noto'g'ri summa! Qaytadan kiriting:")
            return
        state['amount'] = amount
        state['step'] = 'confirm'
        player_info = state.get('player_info', {})
        player_name = player_info.get('Name') or player_info.get('name') or '—'
        bukmeker = state['bukmeker']
        player_id = state['player_id']
        summary = (
            "📦 To'ldirish ma'lumotlari:\n\n"
            f"🏷 Bukmeker: {bukmeker}\n"
            f"🆔 ID: {player_id}\n"
            f"👤 Player: {player_name}\n"
            f"💰 Summa: {amount:,.0f} so'm\n\n"
            "✅ Tasdiqlash tugmasini bosing yoki ❌ Bekor qiling"
        )
        try:
            bot.send_message(ADMIN_ID, summary, reply_markup=get_admin_manual_deposit_confirm_keyboard())
        except Exception as e:
            bot.send_message(ADMIN_ID, f"❌ Xabar yuborilmadi: {e}", reply_markup=get_admin_menu_keyboard())
            del admin_states[ADMIN_ID]
        return

    elif step == 'confirm':
        # Inform admin to use the inline buttons for confirmation/cancel
        safe_send_message(
            bot,
            ADMIN_ID,
            "ℹ️ Tasdiqlash uchun pastdagi tugmalardan foydalaning"
        )
        return

def handle_add_card(bot: telebot.TeleBot, message: Message):
    """Karta qo'shish"""
    if message.text == "🔙 Orqaga":
        del admin_states[ADMIN_ID]
        bot.send_message(ADMIN_ID, "👨‍💼 Admin panel:", reply_markup=get_admin_menu_keyboard())
        return
    
    card_number = message.text.strip().replace(' ', '')
    
    if not validate_card_number(card_number):
        bot.send_message(ADMIN_ID, "❌ Noto'g'ri karta raqam! 16 ta raqam kiriting:")
        return
    
    card = Card(card_number=card_number)
    
    if db.add_card(card):
        last4 = card_number[-4:]
        bot.send_message(
            ADMIN_ID,
            f"✅ Karta qo'shildi: ****{last4}",
            reply_markup=get_admin_menu_keyboard()
        )
    else:
        bot.send_message(
            ADMIN_ID,
            "❌ Karta qo'shilmadi (avval qo'shilgan bo'lishi mumkin)",
            reply_markup=get_admin_menu_keyboard()
        )
    
    del admin_states[ADMIN_ID]

def handle_delete_card(bot: telebot.TeleBot, message: Message):
    """Karta o'chirish"""
    if message.text == "🔙 Orqaga":
        del admin_states[ADMIN_ID]
        bot.send_message(ADMIN_ID, "👨‍💼 Admin panel:", reply_markup=get_admin_menu_keyboard())
        return
    
    card_number = message.text.strip().replace(' ', '')
    
    if not validate_card_number(card_number):
        bot.send_message(ADMIN_ID, "❌ Noto'g'ri karta raqam! 16 ta raqam kiriting:")
        return
    
    if db.delete_card(card_number):
        last4 = card_number[-4:]
        bot.send_message(
            ADMIN_ID,
            f"✅ Karta o'chirildi: ****{last4}",
            reply_markup=get_admin_menu_keyboard()
        )
    else:
        bot.send_message(
            ADMIN_ID,
            "❌ Karta topilmadi yoki allaqachon o'chirilgan",
            reply_markup=get_admin_menu_keyboard()
        )
    
    del admin_states[ADMIN_ID]

def handle_broadcast(bot: telebot.TeleBot, message: Message):
    """Barcha foydalanuvchilarga xabar yuborish (matn/rasm/video)"""
    if message.text == "🔙 Orqaga":
        del admin_states[ADMIN_ID]
        bot.send_message(ADMIN_ID, "👨‍💼 Admin panel:", reply_markup=get_admin_menu_keyboard())
        return
    
    users = db.get_all_users()
    
    if not users:
        bot.send_message(ADMIN_ID, "❌ Foydalanuvchilar yo'q")
        del admin_states[ADMIN_ID]
        return
    
    success_count = 0
    fail_count = 0
    
    status_msg = bot.send_message(ADMIN_ID, f"📤 Xabar yuborilmoqda... 0/{len(users)}")
    
    for i, user in enumerate(users, 1):
        try:
            # Matn xabar
            if message.text and message.text != "🔙 Orqaga":
                bot.send_message(user.user_id, message.text)
                success_count += 1
            # Rasm
            elif message.photo:
                caption = message.caption or ""
                photo = message.photo[-1].file_id
                bot.send_photo(user.user_id, photo, caption=caption)
                success_count += 1
            # Video
            elif message.video:
                caption = message.caption or ""
                video = message.video.file_id
                bot.send_video(user.user_id, video, caption=caption)
                success_count += 1
            # Dokument
            elif message.document:
                caption = message.caption or ""
                document = message.document.file_id
                bot.send_document(user.user_id, document, caption=caption)
                success_count += 1
            # Animation (GIF)
            elif message.animation:
                caption = message.caption or ""
                animation = message.animation.file_id
                bot.send_animation(user.user_id, animation, caption=caption)
                success_count += 1
        except Exception:
            fail_count += 1
        
        # Har 10 ta foydalanuvchidan keyin status yangilash
        if i % 10 == 0 or i == len(users):
            try:
                bot.edit_message_text(
                    f"📤 Xabar yuborilmoqda... {i}/{len(users)}\n✅ Yuborildi: {success_count}\n❌ Xatolik: {fail_count}",
                    ADMIN_ID,
                    status_msg.message_id
                )
            except Exception:
                pass
    
    bot.send_message(
        ADMIN_ID,
        f"✅ Xabar yuborish yakunlandi!\n\n📊 Jami: {len(users)}\n✅ Muvaffaqiyatli: {success_count}\n❌ Xatolik: {fail_count}",
        reply_markup=get_admin_menu_keyboard()
    )
    
    del admin_states[ADMIN_ID]
