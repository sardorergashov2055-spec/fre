import telebot
from telebot.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from database.database import db
from database.models import Withdrawal
from utils.validators import validate_player_id, validate_card_number, validate_code
from utils.keyboards import get_main_menu_keyboard, get_back_keyboard, get_admin_menu_keyboard
import config
from utils.helpers import create_withdrawal_user_message, create_withdrawal_admin_message, log_withdrawal, format_amount, format_datetime
from utils.state_manager import withdrawal_states, deposit_states, last_menu_action, clear_user_states
from config import ADMIN_ID, NOTIFICATION_CHANNEL_ID

# reuse deposit player check
from handlers.deposit import check_player

# API clients
from api.mobcash_api import melbet_api, betwiner_api, winwin_api
from api.xbet_api import xbet_api
from api.mostbet_api import mostbet_api  # Add Mostbet API import

import threading


def _normalize_amount(value):
    """Qiymatni musbat float ga aylantiradi yoki None qaytaradi.
    Qo'llab-quvvatlaydi: int, float, str (bo'sh joy/vergul bilan).
    Manfiy qiymatlar absolyut qiymatga aylantiriladi (withdrawal uchun).
    """
    try:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            v = float(value)
            # Manfiy bo'lsa absolyut qiymat, musbat bo'lsa o'zi
            return abs(v) if v != 0 else None
        if isinstance(value, str):
            s = value.strip().replace(' ', '').replace(',', '')
            if s == '':
                return None
            v = float(s)
            return abs(v) if v != 0 else None
    except Exception:
        return None
    return None
def register_withdrawal_handlers(bot: telebot.TeleBot):
	"""Register withdrawal flow handlers and admin callbacks."""

	# Bukmeker tanlash - faqat withdrawal context da
	@bot.message_handler(func=lambda message: (message.text in ["🎯 1xBet", "🎲 Melbet", "🎰 Mostbet", "🎪 Betwiner", "🎨 WinWinBet"]) and (last_menu_action.get(message.from_user.id) == 'withdrawal'))
	def select_bukmeker_withdrawal(message: Message):
		user_id = message.from_user.id

		# Agar deposit_states da mavjud bo'lsa, bu deposit
		if user_id in deposit_states:
			return

		# Foydalanuvchi withdrawal context da ekanligini tekshirish
		if user_id not in last_menu_action or last_menu_action[user_id] != 'withdrawal':
			return

		bukmeker = message.text.replace("🎯 ", "").replace("🎲 ", "").replace("🎰 ", "").replace("🎪 ", "").replace("🎨 ", "")

		withdrawal_states[user_id] = {
			'action': 'withdrawal',
			'bukmeker': bukmeker,
			'step': 'player_id'
		}

		bot.send_message(
			user_id,
			f"🆔 {bukmeker} ID raqamingizni kiriting:",
			reply_markup=get_back_keyboard()
		)

	@bot.message_handler(func=lambda message: message.from_user.id in withdrawal_states and 
						withdrawal_states[message.from_user.id].get('action') == 'withdrawal')
	def handle_withdrawal_steps(message: Message):
		user_id = message.from_user.id
		state = withdrawal_states[user_id]
		step = state.get('step')

		if message.text == "🔙 Orqaga":
			clear_user_states(user_id)
			# Admin uchun orqaga – admin panel
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

		if step == 'player_id':
			handle_withdrawal_player_id(bot, message)
		elif step == 'code':
			handle_withdrawal_code(bot, message)
		elif step == 'card_number':
			handle_withdrawal_card(bot, message)

	# Admin callback handler - pul o'tkazildi tasdiqlash
	@bot.callback_query_handler(func=lambda call: bool(call.data and call.data.startswith('confirm_withdrawal_')))
	def _handle_confirm_withdrawal(call):
		try:
			if call.from_user.id != ADMIN_ID:
				try:
					bot.answer_callback_query(call.id, "Sizda ruxsat yo'q", show_alert=True)
				except Exception:
					pass
				return

			_id = int(call.data.split('_')[-1])
			w = db.get_withdrawal_by_id(_id)
			if not w:
				bot.answer_callback_query(call.id, "Ariza topilmadi", show_alert=True)
				return

			# Statusni completed ga o'zgartirish
			db.update_withdrawal_status(_id, 'completed')
			
			# Foydalanuvchiga xabar (summa format_amount bilan, qo'shimcha " so'm" YO'Q)
			try:
				amount_text = format_amount(w.amount) if (w.amount is not None and w.amount > 0) else "—"
				bot.send_message(
					w.user_id, 
					f"✅ Pul kartangizga o'tkazildi!\n\n"
					f"💰 Summa: {amount_text}\n"
					f"🆔 {w.bukmeker} ID: {w.player_id}\n\n"
					f"Rahmat! 🎉"
				)
			except Exception:
				pass
			
			# Admindan xabarni o'chirish
			try:
				bot.delete_message(call.message.chat.id, call.message.message_id)
			except Exception:
				pass
			
			# Kanal/notification ga yuborish
			if NOTIFICATION_CHANNEL_ID:
				try:
					user = db.get_user(w.user_id)
					username = getattr(user, 'username', 'username_yoq') if user else 'username_yoq'
					
					amount_text = format_amount(w.amount) if (w.amount is not None and w.amount > 0) else "—"
					notification_msg = (
						f"✅ <b>Pul o'tkazildi</b>\n\n"
						f"<b>#{w.bukmeker}#</b>\n"
						f"👤 @{username}\n"
						f"💰 <b>Summa:</b> {amount_text}\n"
						f"🆔 <b>ID:</b> {w.player_id}\n"
						f"📆 {format_datetime()}"
					)
					bot.send_message(NOTIFICATION_CHANNEL_ID, notification_msg, parse_mode='HTML')
				except Exception:
					pass
			
			# Callback javob
			try:
				bot.answer_callback_query(call.id, "✅ Tasdiqlandi!", show_alert=False)
			except Exception:
				pass
				
		except Exception:
			pass





def handle_withdrawal_player_id(bot: telebot.TeleBot, message: Message):
	"""Player ID tekshirish"""
	user_id = message.from_user.id
	
	if message.text == "🔙 Orqaga":
		clear_user_states(user_id)
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
		bot.send_message(
			user_id,
			"❌ Noto'g'ri ID format!\n\n"
			"✅ To'g'ri format:\n"
			"• Kamida 3 ta belgi\n"
			"• Maksimal 20 ta belgi\n"
			"• Faqat raqam va harflar\n\n"
			"Qaytadan kiriting:"
		)
		return

	bukmeker = withdrawal_states[user_id]['bukmeker']

	# Tekshirish xabari
	checking_msg = None
	try:
		checking_msg = bot.send_message(user_id, "⏳ Tekshirilmoqda...")
	except Exception:
		pass

	# API orqali player tekshirish
	def _async_check_player(u_id: int, bkm: str, p_id: str, check_msg):
		try:
			# Reuse universal player check for consistency with deposit flow
			result = check_player(bkm, p_id)

			# Tekshirish xabarini o'chirish
			try:
				if check_msg:
					bot.delete_message(u_id, check_msg.message_id)
			except Exception:
				pass

			# Agar player topilmasa
			if not result or not result.get('Success'):
				error_msg = result.get('error', 'Player topilmadi') if result else 'API bilan bog\'lanishda xatolik'
				
				bot.send_message(
					u_id,
					f"❌ Player topilmadi!\n\n"
					f"🔍 {error_msg}\n\n"
					f"💡 ID ni to'g'ri kiriting.",
					reply_markup=get_back_keyboard()
				)
				return

			# Player topildi - ism olish va kod so'rash
			player_name = result.get('Name', result.get('name', ''))
			
			withdrawal_states[u_id].update({
				'player_id': p_id,
				'player_name': player_name,
				'step': 'code'
			})

			# Agar ism bo'lsa ko'rsatamiz
			if player_name:
				bot.send_message(
					u_id,
					f"✅ Player topildi: {player_name}\n\n"
					f"🔢 {bkm} tomonidan berilgan maxsus kodni kiriting:",
					reply_markup=get_back_keyboard()
				)
			else:
				bot.send_message(
					u_id,
					f"🔢 {bkm} tomonidan berilgan maxsus kodni kiriting:",
					reply_markup=get_back_keyboard()
				)

		except Exception:
			try:
				bot.send_message(
					u_id,
					"❌ Xatolik yuz berdi. Qaytadan urinib ko'ring.",
					reply_markup=get_back_keyboard()
				)
			except Exception:
				pass

	# Background thread
	threading.Thread(
		target=_async_check_player,
		args=(user_id, bukmeker, player_id, checking_msg),
		daemon=True
	).start()


def handle_withdrawal_code(bot: telebot.TeleBot, message: Message):
	"""Kod kiritish va payout tekshirish"""
	user_id = message.from_user.id
	code = message.text.strip()

	if not validate_code(code):
		bot.send_message(user_id, "❌ Noto'g'ri kod! 4 ta raqam kiriting:")
		return

	state = withdrawal_states[user_id]
	bukmeker = state['bukmeker']
	player_id = state['player_id']

	# Payout tekshirish xabari
	checking_msg = None
	try:
		checking_msg = bot.send_message(user_id, "⏳ Tekshirilmoqda...")
	except Exception:
		pass

	# API orqali payout tekshirish
	def _async_check_payout(u_id: int, bkm: str, p_id: str, payout_code: str, check_msg):
		try:
			result = None
			try:
				if bkm == "1xBet" and xbet_api:
					result = xbet_api.deposit_payout(p_id, payout_code)
				elif bkm == "Melbet" and melbet_api:
					result = melbet_api.withdraw_subtract(p_id, payout_code)
				elif bkm == "Betwiner" and betwiner_api:
					result = betwiner_api.withdraw_subtract(p_id, payout_code)
				elif bkm == "WinWinBet" and winwin_api:
					result = winwin_api.withdraw_subtract(p_id, payout_code)
				elif bkm == "Mostbet" and mostbet_api:
					# Mostbet uchun manual approval
					result = {'Success': True, 'Amount': 0}
			except Exception:
				result = None

			# Tekshirish xabarini o'chirish
			try:
				if check_msg:
					bot.delete_message(u_id, check_msg.message_id)
			except Exception:
				pass

			# Agar payout topilmasa
			if not result or not result.get('Success'):
				try:
					bot.send_message(
						u_id,
						f"🆔 {bkm} UZS ID: {p_id}\n"
						f"#️⃣ 4 talik kod: {payout_code}\n\n"
						f"📆 Vaqt: {format_datetime()}\n\n"
						f"❌ Siz tomondan pul chiqarishga ariza ochilmagan!\n"
						f"Pul yechish manzili quydagi kanalda @fjhfh\n"
						f"Bosh sahifaga qaytish - /start",
						reply_markup=get_main_menu_keyboard()
					)
					clear_user_states(u_id)
				except Exception as e:
					# Agar xabar yuborishda xatolik bo'lsa, hech bo'lmaganda state tozalaymiz
					clear_user_states(u_id)
				return

			# ✅ Payout topildi va API orqali muvaffaqiyatli bajarildi
			# Turli API javoblari uchun mos kalitlardan olish
			amount = (
				result.get('Amount') if result.get('Amount') is not None else
				result.get('summa') if result.get('summa') is not None else
				result.get('Summa') if result.get('Summa') is not None else
				result.get('Sum') if result.get('Sum') is not None else
				result.get('amount') if result.get('amount') is not None else
				None
			)
			# amount ni xavfsiz normalizatsiya qilish (manfiy bo'lsa absolyut)
			amount_norm = _normalize_amount(amount)
			
			# Karta so'rash
			withdrawal_states[u_id].update({
				'code': payout_code,
				'amount': amount_norm,
				'step': 'card_number'
			})

			bot.send_message(
				u_id,
				f"💳 Karta raqamingizni kiriting (16 ta raqam):",
				reply_markup=get_back_keyboard()
			)

		except Exception:
			try:
				bot.send_message(
					u_id,
					"❌ Xatolik yuz berdi. Qaytadan urinib ko'ring.",
					reply_markup=get_back_keyboard()
				)
			except Exception:
				pass

	# Background thread
	threading.Thread(
		target=_async_check_payout,
		args=(user_id, bukmeker, player_id, code, checking_msg),
		daemon=True
	).start()


def handle_withdrawal_card(bot: telebot.TeleBot, message: Message):
	"""Karta raqamini qabul qilish va withdrawal yaratish"""
	user_id = message.from_user.id
	card_number = message.text.strip().replace(' ', '')

	if not validate_card_number(card_number):
		bot.send_message(user_id, "❌ Noto'g'ri karta raqam! 16 ta raqam kiriting:")
		return

	state = withdrawal_states[user_id]
	bukmeker = state['bukmeker']
	player_id = state['player_id']
	code = state['code']
	amount = state.get('amount')

	# Agar amount yo'q bo'lsa (Mostbet yoki API qaytarmagan), None saqlaymiz
	if not amount or amount <= 0:
		amount = None

	# Withdrawal ni bazaga saqlash (None bo'lsa NULL yoziladi, placeholder ishlatilmaydi)
	try:
		amount_for_store = _normalize_amount(amount)
		withdrawal = Withdrawal(
			user_id=user_id,
			bukmeker=bukmeker,
			player_id=player_id,
			card_number=card_number,
			code=code,
			amount=amount_for_store
		)
	except ValueError as e:
		bot.send_message(
			user_id,
			f"❌ Xatolik: {str(e)}\n\nQaytadan urinib ko'ring.",
			reply_markup=get_main_menu_keyboard()
		)
		clear_user_states(user_id)
		return

	withdrawal_id = db.add_withdrawal(withdrawal)
	if not withdrawal_id:
		bot.send_message(
			user_id,
			"❌ Xatolik yuz berdi. Qaytadan urinib ko'ring.",
			reply_markup=get_main_menu_keyboard()
		)
		clear_user_states(user_id)
		return

	# Log attempt
	try:
		log_withdrawal({
			'user_id': user_id,
			'withdrawal_id': withdrawal_id,
			'bukmeker': bukmeker,
			'player_id': player_id,
			'card_last4': card_number[-4:] if card_number else None,
			'code': code,
			'status': 'pending'
		})
	except Exception:
		pass

	# Foydalanuvchiga xabar
	user_message = create_withdrawal_user_message(bukmeker, player_id, card_number, code)
	bot.send_message(user_id, user_message, reply_markup=get_main_menu_keyboard())

	# Adminga ma'lumot yuborish (tasdiqlash tugmasi bilan)
	user = db.get_user(user_id)
	username = getattr(user, 'username', 'username_yoq') if user else 'username_yoq'
	
	admin_amount = _normalize_amount(amount)
	admin_message = create_withdrawal_admin_message(
		username, bukmeker, player_id, card_number, code, admin_amount
	)
	
	# Tasdiqlash tugmasi
	markup = InlineKeyboardMarkup()
	markup.row(
		InlineKeyboardButton("✅ Pul o'tkazildi", callback_data=f"confirm_withdrawal_{withdrawal_id}")
	)
	
	try:
		bot.send_message(ADMIN_ID, admin_message, reply_markup=markup, parse_mode='HTML')
	except Exception:
		pass

	clear_user_states(user_id)




