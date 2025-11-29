"""Soddalashtirilgan global state manager.

Maqsad:
 - Foydalanuvchi jarayonlari (depozit, yechish, admin) davomida boshqa handlerlar aralashmasin.
 - Minimal API: clear_user_states, get_user_context, is_user_in_process.

Kelajak (ixtiyoriy) tavsiyalar:
 - Thread-safety uchun Lock (agar bir vaqtda ko'p oqim yozsa) qo'shish.
 - TTL bilan avtomatik eskirish (uzoq turib qolgan yarim jarayonlarni tozalash).
 - Enum ("deposit", "withdrawal", "admin") o'rniga qat'iy tip.
"""

# Menu context tracking
last_menu_action = {}

# Deposit states
deposit_states = {}

# Withdrawal states
withdrawal_states = {}

# Admin states
admin_states = {}

def clear_user_states(user_id: int) -> None:
    """Foydalanuvchining barcha state larini tozalash.

    O'zgarish: return tipi aniqligi (-> None) va kod ixchamlashtirildi.
    """
    for container in (last_menu_action, deposit_states, withdrawal_states, admin_states):
        container.pop(user_id, None)

def get_user_context(user_id: int) -> str:
    """Foydalanuvchining hozirgi contextini aniqlash.

    Tartib ustuvorligi: deposit > withdrawal > admin > menu > main
    """
    if user_id in deposit_states:
        return "deposit"
    if user_id in withdrawal_states:
        return "withdrawal"
    if user_id in admin_states:
        return "admin"
    return last_menu_action.get(user_id, "main")

def is_user_in_process(user_id: int) -> bool:
    """Foydalanuvchi aktiv jarayon ichidami (depozit/yechish/admin)."""
    return any(user_id in container for container in (deposit_states, withdrawal_states, admin_states))
