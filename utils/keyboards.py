"""Klaviatura generatorlari.

Bu modul botdagi barcha reply/inline klaviaturalarning markaziy manbai.
Optimallashtirishlar:
 - Takroriy kod minimal: har bir funksiyada faqat kerakli tugmalar.
 - Admin va oddiy foydalanuvchi menyulari aniq ajratilgan.
 - Katta o'zgarish yo'q, faqat izoh va kelajakdagi kengaytirish uchun barqarorlik.
"""

from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

def get_phone_request_keyboard():
    """Telefon raqam so'rash klaviaturasi"""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    phone_button = KeyboardButton("📱 Telefon raqamni yuborish", request_contact=True)
    keyboard.add(phone_button)
    return keyboard

def get_main_menu_keyboard():
    """Asosiy foydalanuvchi menyu klaviaturasi.

    Tarkib: depozit, yechish, ilovalar, aloqa.
    """
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row("💰 Hisob to'ldirish", "💸 Pul yechish")
    keyboard.row("📱 Ilovalar", "📞 Aloqa")
    return keyboard

def get_main_menu_keyboard_admin():
    """Admin uchun foydalanuvchi menyusi + admin panel tugmasi."""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row("💰 Hisob to'ldirish", "💸 Pul yechish")
    keyboard.row("📱 Ilovalar", "📞 Aloqa")
    keyboard.row("👨‍💼 Admin panel")
    return keyboard

def get_admin_menu_keyboard():
    """Admin panel klaviaturasi.

    Qamrab oladi: depozit/yechish (tezkor), qo'lda to'ldirish, statistika,
    xabar yuborish, bot holati, karta boshqaruvi va kassa balans.
    """
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row("💰 Hisob to'ldirish", "💸 Pul yechish")
    keyboard.row("✋ Qo'lda to'ldirish", "📊 Statistika")
    keyboard.row("📢 Xabar yuborish", "🔧 Bot o'chirish")
    keyboard.row("💳 Karta qo'shish", "💰 Kasa balansi")
    return keyboard

def get_bookmakers_keyboard():
    """Bukmeker tanlash klaviaturasi."""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row("🎯 1xBet", "🎲 Melbet")
    keyboard.row("🎪 Betwiner", "🎨 WinWinBet")
    keyboard.row("🔙 Orqaga")
    return keyboard

def get_back_keyboard():
    """Oddiy orqaga qaytish klaviaturasi."""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add("🔙 Orqaga")
    return keyboard

def get_cancel_keyboard():
    """Bekor qilish uchun inline tugma."""
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel_payment"))
    return keyboard

def get_admin_confirmation_keyboard(withdrawal_id: int):
    """Pul yechish jarayonini admin tasdiqlashi uchun inline tugma."""
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"approve_withdrawal_{withdrawal_id}"))
    return keyboard

def get_card_management_keyboard():
    """Karta boshqaruv (CRUD) klaviaturasi."""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row("➕ Karta qo'shish", "❌ Karta o'chirish")
    keyboard.row("📋 Kartalar ro'yxati", "🔙 Orqaga")
    return keyboard

def get_balance_keyboard():
    """Balans yangilash va orqaga tugmalari."""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row("🔄 Yangilash")
    keyboard.row("🔙 Orqaga")
    return keyboard

def get_urls_keyboard():
    """Static admin URL inline klaviaturasi (keyinchalik config dan kelishi mumkin)."""
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("👨‍💼 Admin", url="https://t.me/your_admin"))
    return keyboard

def get_apps_keyboard():
    """Ilovalar (app/channel) URL inline klaviatura."""
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("📱 Ilovalar", url="https://t.me/your_apps_channel"))
    return keyboard


def get_admin_manual_deposit_confirm_keyboard():
    """Qo'lda to'ldirishni yakunlash uchun tasdiq/bekor inline klaviatura."""
    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton("✅ Tasdiqlash", callback_data="admin_md_confirm"),
        InlineKeyboardButton("❌ Bekor qilish", callback_data="admin_md_cancel")
    )
    return keyboard

