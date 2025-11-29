from datetime import datetime
from typing import Optional
from dataclasses import dataclass, field

@dataclass
class User:
    """Foydalanuvchi modeli"""
    user_id: int
    username: Optional[str] = None
    phone: Optional[str] = None
    first_name: Optional[str] = None
    is_admin: bool = False
    created_at: datetime = field(default_factory=datetime.now)
    
    def __post_init__(self):
        """Validatsiya"""
        if not isinstance(self.user_id, int):
            raise ValueError("user_id must be an integer")
        if self.user_id <= 0:
            raise ValueError("user_id must be positive")
    
    def to_dict(self) -> dict:
        """Dict formatga o'tkazish"""
        return {
            'user_id': self.user_id,
            'username': self.username,
            'phone': self.phone,
            'first_name': self.first_name,
            'is_admin': self.is_admin,
            'created_at': self.created_at.isoformat()
        }
    
    def __str__(self):
        return f"User(id={self.user_id}, username={self.username})"

@dataclass
class Payment:
    """To'lov modeli"""
    user_id: int
    bukmeker: str
    player_id: str
    amount: float
    payment_id: str
    card_last4: Optional[str] = None
    status: str = "pending"  # pending, completed, failed, expired
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    # Optional message identifiers for the payment message sent to the user
    payment_chat_id: Optional[int] = None
    payment_message_id: Optional[int] = None
    
    def __post_init__(self):
        """Validatsiya"""
        if not isinstance(self.user_id, int):
            raise ValueError("user_id must be an integer")
        
        if self.amount <= 0:
            raise ValueError("amount must be positive")
        
        if not self.payment_id:
            raise ValueError("payment_id cannot be empty")
        
        if self.card_last4 and len(self.card_last4) != 4:
            raise ValueError("card_last4 must be 4 digits")
        
        valid_statuses = ['pending', 'completed', 'failed', 'expired']
        if self.status not in valid_statuses:
            raise ValueError(f"status must be one of {valid_statuses}")
    
    def mark_completed(self):
        """To'lovni completed qilish"""
        self.status = "completed"
        self.updated_at = datetime.now()
    
    def mark_failed(self):
        """To'lovni failed qilish"""
        self.status = "failed"
        self.updated_at = datetime.now()
    
    def mark_expired(self):
        """To'lovni expired qilish"""
        self.status = "expired"
        self.updated_at = datetime.now()
    
    def is_pending(self) -> bool:
        """Pending holatda ekanligini tekshirish"""
        return self.status == "pending"
    
    def to_dict(self) -> dict:
        """Dict formatga o'tkazish"""
        return {
            'user_id': self.user_id,
            'bukmeker': self.bukmeker,
            'player_id': self.player_id,
            'amount': self.amount,
            'payment_id': self.payment_id,
            'card_last4': self.card_last4,
            'status': self.status,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'payment_chat_id': self.payment_chat_id,
            'payment_message_id': self.payment_message_id
        }
    
    def __str__(self):
        return f"Payment(id={self.payment_id}, amount={self.amount}, status={self.status})"

@dataclass
class Withdrawal:
    """Pul yechish modeli"""
    user_id: int
    bukmeker: str
    player_id: str
    card_number: str
    code: str
    amount: Optional[float] = None
    status: str = "pending"  # pending, approved, completed, failed
    created_at: datetime = field(default_factory=datetime.now)
    id: Optional[int] = None
    
    def __post_init__(self):
        """Validatsiya"""
        if not isinstance(self.user_id, int):
            raise ValueError("user_id must be an integer")
        
        if not self.card_number:
            raise ValueError("card_number cannot be empty")
        
        # Karta raqamini faqat raqamlardan iboratligi
        clean_card = self.card_number.replace(" ", "")
        if not clean_card.isdigit():
            raise ValueError("card_number must contain only digits")
        
        if len(clean_card) != 16:
            raise ValueError("card_number must be 16 digits")
        
        if not self.code:
            raise ValueError("code cannot be empty")
        
        if self.amount is not None and self.amount <= 0:
            raise ValueError("amount must be positive")
        
        valid_statuses = ['pending', 'approved', 'completed', 'failed']
        if self.status not in valid_statuses:
            raise ValueError(f"status must be one of {valid_statuses}")
    
    def mark_approved(self):
        """Withdrawal ni approved qilish"""
        self.status = "approved"
    
    def mark_completed(self):
        """Withdrawal ni completed qilish"""
        self.status = "completed"
    
    def mark_failed(self):
        """Withdrawal ni failed qilish"""
        self.status = "failed"
    
    def is_pending(self) -> bool:
        """Pending holatda ekanligini tekshirish"""
        return self.status == "pending"
    
    def get_masked_card(self) -> str:
        """Karta raqamini mask qilish"""
        clean_card = self.card_number.replace(" ", "")
        return f"{clean_card[:4]} **** **** {clean_card[-4:]}"
    
    def to_dict(self) -> dict:
        """Dict formatga o'tkazish"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'bukmeker': self.bukmeker,
            'player_id': self.player_id,
            'card_number': self.card_number,
            'code': self.code,
            'amount': self.amount,
            'status': self.status,
            'created_at': self.created_at.isoformat()
        }
    
    def __str__(self):
        return f"Withdrawal(id={self.id}, card={self.get_masked_card()}, status={self.status})"

@dataclass
class Card:
    """Karta modeli"""
    card_number: str
    card_name: Optional[str] = None
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    id: Optional[int] = None
    
    def __post_init__(self):
        """Validatsiya"""
        if not self.card_number:
            raise ValueError("card_number cannot be empty")
        
        # Karta raqamini faqat raqamlardan iboratligi
        clean_card = self.card_number.replace(" ", "")
        if not clean_card.isdigit():
            raise ValueError("card_number must contain only digits")
        
        if len(clean_card) != 16:
            raise ValueError("card_number must be 16 digits")
    
    def get_last4(self) -> str:
        """Karta raqamining oxirgi 4 raqamini olish"""
        clean_card = self.card_number.replace(" ", "")
        return clean_card[-4:]
    
    def get_masked_number(self) -> str:
        """Karta raqamini mask qilish"""
        clean_card = self.card_number.replace(" ", "")
        return f"{clean_card[:4]} **** **** {clean_card[-4:]}"
    
    def get_formatted_number(self) -> str:
        """Karta raqamini formatlash (4-4-4-4)"""
        clean_card = self.card_number.replace(" ", "")
        return f"{clean_card[:4]} {clean_card[4:8]} {clean_card[8:12]} {clean_card[12:]}"
    
    def activate(self):
        """Kartani aktivlashtirish"""
        self.is_active = True
    
    def deactivate(self):
        """Kartani deaktivlashtirish"""
        self.is_active = False
    
    def toggle_status(self):
        """Karta statusini o'zgartirish"""
        self.is_active = not self.is_active
    
    def to_dict(self) -> dict:
        """Dict formatga o'tkazish"""
        return {
            'id': self.id,
            'card_number': self.card_number,
            'card_name': self.card_name,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat()
        }
    
    def __str__(self):
        status = "Active" if self.is_active else "Inactive"
        return f"Card({self.get_masked_number()}, {status})"

# Utility funksiyalar
def validate_card_number(card_number: str) -> bool:
    """Karta raqamini validatsiya qilish"""
    try:
        clean_card = card_number.replace(" ", "")
        return len(clean_card) == 16 and clean_card.isdigit()
    except:
        return False

def format_amount(amount: float) -> str:
    """Summani formatlash"""
    return f"{amount:,.0f}".replace(",", " ")

def parse_payment_format(text: str) -> Optional[dict]:
    """PAYMENT|SUMMA|KARTA4 formatni parse qilish"""
    try:
        parts = text.strip().split('|')
        
        if len(parts) != 3 or parts[0] != 'PAYMENT':
            return None
        
        amount = float(parts[1])
        card_last4 = parts[2]
        
        if len(card_last4) != 4 or not card_last4.isdigit():
            return None
        
        return {
            'amount': amount,
            'card_last4': card_last4,
            'timestamp': datetime.now()
        }
        
    except (ValueError, IndexError):
        return None
