"""Validatorlar moduli.

Maqsad: foydalanuvchi kiruvchi ma'lumotlarini tekshirish (player_id, amount, karta, kod, telefon, username).
Optimallashtirish:
 - Regex compile bir martalik (modul darajasida).
 - Tuple return tipi aniqlanadi: (bool, int) uchun validate_amount.
 - Docstringlar va izohlar kengaytirildi.
"""

import re
from typing import Tuple

# Regex'larni bir marta compile qilib, performance yaxshilash
_PLAYER_ID_PATTERN = re.compile(r'^[a-zA-Z0-9._-]+$')
_USERNAME_PATTERN = re.compile(r'^[a-zA-Z0-9_]+$')


def validate_player_id(player_id: str) -> bool:
    """Player ID ni tekshirish (3-20 belgi, raqam/harf va ._- ruxsat).
    
    Args:
        player_id: O'yinchi identifikatori.
    
    Returns:
        bool: To'g'ri bo'lsa True, aks holda False.
    """
    if not player_id:
        return False
    
    player_id = player_id.strip()
    if not (3 <= len(player_id) <= 20):
        return False
    
    return bool(_PLAYER_ID_PATTERN.match(player_id))


def validate_amount(amount_text: str, min_amount: int, max_amount: int) -> Tuple[bool, int]:
    """Summa tekshirish va int ga aylantirish.
    
    Args:
        amount_text: Kiruvchi matn (probel, vergul, nuqta tozalanadi).
        min_amount: Minimal ruxsat etilgan summa.
        max_amount: Maksimal ruxsat etilgan summa.
    
    Returns:
        Tuple[bool, int]: (True, summa) agar to'g'ri bo'lsa; aks holda (False, 0).
    """
    try:
        # Matn tozalash: probel, vergul, nuqta
        amount_text = amount_text.strip().replace(' ', '').replace(',', '').replace('.', '')
        amount = int(amount_text)
        
        # Diapazonda ekanligini tekshirish
        if not (min_amount <= amount <= max_amount):
            return False, 0
        
        return True, amount
    except (ValueError, AttributeError):
        return False, 0



def validate_card_number(card_number: str) -> bool:
    """Karta raqam tekshirish (16 raqam, probel/tirnoq tozalanadi).
    
    Args:
        card_number: Karta raqami (16 ta raqam).
    
    Returns:
        bool: To'g'ri bo'lsa True, aks holda False.
    """
    if not card_number:
        return False
    
    card_number = card_number.strip().replace(' ', '').replace('-', '')
    return len(card_number) == 16 and card_number.isdigit()



def validate_code(code: str) -> bool:
    """4 raqamli yoki provider-specific kod tekshirish.
    
    Provayderlar turli kod formatlarini talab qilishi mumkin;
    shuning uchun 1-64 belgigacha qabul qilamiz (bo'sh emas).
    
    Args:
        code: Tasdiq kodi.
    
    Returns:
        bool: To'g'ri bo'lsa True, aks holda False.
    """
    if not code:
        return False
    
    code = code.strip()
    return 1 <= len(code) <= 64



def validate_phone(phone: str) -> bool:
    """Telefon raqam tekshirish (9-15 raqam, +, probel, tirnoq, qavslar tozalanadi).
    
    Args:
        phone: Telefon raqami.
    
    Returns:
        bool: To'g'ri bo'lsa True, aks holda False.
    """
    if not phone:
        return False
    
    phone = phone.strip().replace('+', '').replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
    return 9 <= len(phone) <= 15 and phone.isdigit()



def validate_telegram_username(username: str) -> bool:
    """Telegram username tekshirish (5-32 belgi, raqam, harf va _ ruxsat, @ tozalanadi).
    
    Args:
        username: Telegram foydalanuvchi nomi.
    
    Returns:
        bool: To'g'ri bo'lsa True, aks holda False.
    """
    if not username:
        return False
    
    username = username.strip().replace('@', '')
    return 5 <= len(username) <= 32 and bool(_USERNAME_PATTERN.match(username))

