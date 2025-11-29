import random
from datetime import datetime
from typing import List, Optional
from database.models import Card

def generate_payment_id() -> str:
    """To'lov ID generatsiya qilish"""
    return str(random.randint(10000, 99999))

def generate_random_amount(min_val: int = 1, max_val: int = 125) -> int:
    """Random summa generatsiya qilish"""
    return random.randint(min_val, max_val)

def get_random_card(cards: List[Card]) -> Optional[Card]:
    """Random karta tanlash"""
    if not cards:
        return None
    return random.choice(cards)

def format_datetime(dt: datetime = None) -> str:
    """Sana va vaqtni formatlash"""
    if dt is None:
        dt = datetime.now()
    return dt.strftime("%Y-%m-%d %H:%M:%S")

def format_card_number(card_number: str) -> str:
    """Karta raqamini formatlash (4-4-4-4)"""
    if len(card_number) == 16:
        return f"{card_number[:4]} {card_number[4:8]} {card_number[8:12]} {card_number[12:]}"
    return card_number

def get_payment_timeout_message(minutes: int = 5) -> str:
    """To'lov muddati xabari"""
    return f"🕒 To'lov muddati: {minutes} daqiqa"

def create_payment_message_html(bukmeker: str, player_id: str, card_number: str, 
                                final_amount: float, user_amount: float, payment_id: str, 
                                user_id: int) -> str:
    """To'lov oynasi xabari (HTML format, copy-paste uchun)"""
    
    # Karta raqamini formatlash
    formatted_card = format_card_number(card_number)
    
    message = (
        f"💳 <b>To'lov ma'lumotlari</b>\n\n"
        f"<b>Bukmeker:</b> {bukmeker}\n"
        f"<b>ID:</b> <code>{player_id}</code>\n"
        f"<b>Karta:</b> <code>{formatted_card}</code>\n\n"
        f"<b>To'lash kerak:</b> <code>{final_amount:,.0f}</code> so'm\n"
        f"✅ <b>Bu summani yubormang:</b> <code>{user_amount:,.0f}</code> so'm ❌\n\n"
        f"🕒 To'lov muddati: 5 daqiqa\n"
        f"TG ID: <code>{user_id}</code>\n"
        f"To'lov ID: <code>{payment_id}</code>"
    )
    
    return message

def create_payment_message(bukmeker: str, player_id: str, card_number: str, 
                         final_amount: float, user_amount: float, payment_id: str, 
                         user_id: int) -> str:
    """To'lov oynasi xabari (oddiy format, compatibility uchun)"""
    
    message = f"""💳 To'lov ma'lumotlari

Bukmeker: {bukmeker}
ID: {player_id}
Karta: {card_number}

To'lash kerak: {final_amount:,.0f} so'm
✅ Bu summani yubormang: {user_amount:,.0f} so'm ❌

{get_payment_timeout_message()}
TG ID: {user_id}
To'lov ID: {payment_id}"""
    
    return message

def create_success_message(bukmeker: str, player_id: str, amount: float) -> str:
    """Muvaffaqiyatli to'lov xabari (HTML format)"""
    return (
        f"✅ <b>Operatsiya muvaffaqiyatli o'tdi!</b>\n\n"
        f"<b>Bukmeker:</b> {bukmeker}\n"
        f"<b>ID:</b> <code>{player_id}</code>\n"
        f"💵 <b>Summa:</b> <code>{amount:,.0f}</code> so'm\n"
        f"<b>To'lov tizimi komissiyasi:</b> 0%\n\n"
        f"Bot: @uzpaykassa_bot"
    )

def create_withdrawal_user_message(bukmeker: str, player_id: str, card_number: str, 
                                 code: str) -> str:
    """Pul yechish foydalanuvchi xabari (oddiy matn, HTML tagsiz)."""
    formatted_card = format_card_number(card_number)

    return (
        f"✅ Arizangiz qabul qilindi!\n\n"
        f"💳 Karta: {formatted_card}\n"
        f"💸 Valyuta: UZS\n"
        f"🆔 {bukmeker} ID: {player_id}\n"
        f"#️⃣ 4 talik kod: {code}\n"
        f"📆 Vaqt: {format_datetime()}\n\n"
        f"So'rovingiz adminga yuborildi!\n"
        f"Bosh sahifaga qaytish - /start"
    )

def create_withdrawal_admin_message(username: str, bukmeker: str, player_id: str, 
                                  card_number: str, code: str, amount: float) -> str:
    """Pul yechish admin xabari (HTML format)"""
    formatted_card = format_card_number(card_number)
    # Handle None amount gracefully
    if amount is None:
        amount_display = "—"
    else:
        try:
            amount_display = f"{amount:,.0f}"
        except Exception:
            amount_display = str(amount)

    return (
        f"✅ <b>Yechish muvaffaqiyatli bajarildi</b>\n\n"
        f"<b>#{bukmeker}#</b>\n"
        f"👤 <b>Foydalanuvchi:</b> @{username}\n"
        f"💳 <b>Foydalanuvchi kartasi:</b> <code>{card_number}</code>\n"
        f"💵 <b>Yechilgan summa:</b> <code>{amount_display}</code> so'm\n"
        f"🆔 <b>{bukmeker} ID:</b> <code>{player_id}</code>\n"
        f"📆 <b>Vaqt:</b> {format_datetime()}"
    )

def create_channel_payment_message(payment_id: str, amount: float, username: str, 
                                 phone: str, balance: float, limit: float, 
                                 bukmeker: str, success: bool = True) -> str:
    """Kanal to'lov xabari (HTML format)"""
    status = "✅ MUVAFFAQIYATLI" if success else "🚫 Kasa puli tugagan"
    
    return (
        f"📋 <b>To'lov #{payment_id}</b>\n"
        f"💰 <b>Summa:</b> <code>{amount:,.0f}</code> so'm\n"
        f"👤 <b>Mijoz:</b> @{username}\n"
        f"📞 <b>Tel:</b> <code>{phone}</code>\n"
        f"🏦 <b>Kassa:</b>\n"
        f"   • <b>Balans:</b> <code>{balance:,.0f}</code>\n"
        f"   • <b>Limit:</b> <code>{limit:,.0f}</code>\n"
        f"{status} | <b>{bukmeker}</b>"
    )

def create_balance_message(balances: dict) -> str:
    """Kassa balanslari xabari (HTML format)"""
    message = "💰 KASSA BALANSLARI\n\n"
    
    for bukmeker, data in balances.items():
        if data.get('Success'):
            balance = data.get('Balance', 0)
            limit = data.get('Limit', 0)
            imperium_balance = data.get('ImperiumBalance', 0)
            
            message += f"🎯 {bukmeker}:\n"
            message += f"   💵 Balans: {balance:,.0f} so'm\n"
            message += f"   📊 Limit: {limit:,.0f} so'm\n"
            
            # ImperiumBalance borligini tekshirish va ko'rsatish
            if imperium_balance > 0:
                message += f"   💎 Imperium: {imperium_balance:,.0f} so'm\n"
            
            message += "\n"
        else:
            # Xato xabarlarini o'zbek tilida ko'rsatish
            error_raw = data.get('error', data.get('Error', ''))
            error = str(error_raw)
            
            # Umumiy xato xabarlari
            lower_err = error.lower()
            if 'javob bermadi' in lower_err or 'timeout' in lower_err:
                message += f"⏱ {bukmeker}: Server javob bermadi\n\n"
            elif 'connection' in lower_err or 'ulanib' in lower_err:
                message += f"🔌 {bukmeker}: Serverga ulanib bo'lmadi\n\n"
            elif bukmeker.lower() == 'mostbet':
                message += f"❌ {bukmeker}: Xatolik\n\n"
            else:
                error_code = data.get('ErrorCode', '')
                if error_code:
                    message += f"❌ {bukmeker}: {error} (kod: {error_code})\n\n"
                else:
                    message += f"❌ {bukmeker}: {error if error else 'Noma\'lum xato'}\n\n"
    
    return message

def create_stats_message(users_count: int, today_payments: int, today_amount: float) -> str:
    """Statistika xabari (HTML format)"""
    return (
        f"📊BOT STATISTIKASI\n\n"
        f"👥Foydalanuvchilar:{users_count}\n"
        f"💰Bugungi to'lovlar:{today_payments}\n"
        f"Bugungi summa:{today_amount:,.0f} so'm"
    )

def create_admin_notification(payment_id: str, bukmeker: str, player_id: str, 
                            amount: float, username: str, user_id: int) -> str:
    """Admin uchun to'lov bildirishnomasi (HTML format)"""
    return (
        f"🔔 Yangi to'lov so'rovi\n\n"
        f"Bukmeker: {bukmeker}\n"
        f"O'yinchi ID: {player_id}\n"
        f"Summa: {amount:,.0f} so'm\n\n"
        f"Foydalanuvchi: @{username}\n"
        f"TG ID: {user_id}\n"
        f"To'lov ID: {payment_id}"
    )

def create_card_display(card_number: str, show_full: bool = False) -> str:
    """Karta raqamini ko'rsatish"""
    if show_full:
        return format_card_number(card_number)
    else:
        # Faqat oxirgi 4 raqamni ko'rsatish
        return f"**** **** **** {card_number[-4:]}"

def get_bukmeker_emoji(bukmeker: str) -> str:
    """Bukmeker emoji olish"""
    emojis = {
        "1xBet": "🎯",
        "Melbet": "🎲", 
        "Betwiner": "🎪",
        "WinWinBet": "🎨"
    }
    return emojis.get(bukmeker, "🎲")

def get_bukmeker_name_with_emoji(bukmeker: str) -> str:
    """Emoji bilan bukmeker nomi"""
    emoji = get_bukmeker_emoji(bukmeker)
    return f"{emoji} {bukmeker}"

def create_timeout_message(payment_id: str) -> str:
    """To'lov muddati tugaganda xabar"""
    return (
        f"⏰To'lov muddati tugadi!\n\n"
        f"To'lov ID: {payment_id}\n"
        f"Iltimos, qaytadan urinib ko'ring."
    )

def create_cancelled_message(payment_id: str) -> str:
    """To'lov bekor qilinganda xabar"""
    return (
        f"❌To'lov bekor qilindi\n\n"
        f"To'lov ID:{payment_id}"
    )

def validate_uzbek_card(card_number: str) -> bool:
    """O'zbek karta raqamini tekshirish"""
    # Karta raqami 16 ta raqam bo'lishi kerak
    if len(card_number) != 16 or not card_number.isdigit():
        return False
    
    # O'zbekiston kartalarining prefikslari
    uzbek_prefixes = [
        '8600',  # UzCard
        '5614',  # Humo
        '9860',  # Humo
    ]
    
    return any(card_number.startswith(prefix) for prefix in uzbek_prefixes)

def mask_sensitive_data(text: str, show_last: int = 4) -> str:
    """Maxfiy ma'lumotlarni yashirish"""
    if len(text) <= show_last:
        return text
    
    masked_part = '*' * (len(text) - show_last)
    visible_part = text[-show_last:]
    
    return f"{masked_part}{visible_part}"

def format_amount(amount: float, currency: str = "so'm") -> str:
    """Summani formatlash"""
    return f"{amount:,.0f} {currency}"

def get_current_timestamp() -> str:
    """Joriy vaqt tamg'asi"""
    return datetime.now().strftime("%Y%m%d_%H%M%S")

def create_receipt_message(payment_id: str, bukmeker: str, player_id: str, 
                         amount: float, card_last4: str) -> str:
    """To'lov kvitansiyasi"""
    return (
        f"🧾 TO'LOV KVITANSIYASI\n\n"
        f"📄 ID: {payment_id}\n"
        f"🎲 Bukmeker: {bukmeker}\n"
        f"👤 O'yinchi ID: {player_id}\n"
        f"💰 Summa: {amount:,.0f} so'm\n"
        f"💳 Karta: **** **** **** {card_last4}\n"
        f"📅 Sana: {format_datetime()}\n"
        f"✅ <b>Status:</b> Muvaffaqiyatli"
    )


def log_manual_deposit(entry: dict) -> None:
    """No-op for performance: previously wrote to logs/manual_deposits.log.

    Keeping the function to avoid import/call-site changes.
    """
    return


def log_withdrawal(entry: dict) -> None:
    """No-op for performance: previously wrote to logs/withdrawals.log.

    Keeping the function to avoid import/call-site changes.
    """
    return

