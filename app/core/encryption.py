# app/core/encryption.py

from sqlalchemy import TypeDecorator, Text
from cryptography.fernet import Fernet


class EncryptedText(TypeDecorator):
    impl = Text
    cache_ok = True

    def __init__(self):
        super().__init__()
        from app.core.config import settings
        key = settings.ENCRYPTION_KEY
        if not key:
            raise ValueError("ENCRYPTION_KEY not set in environment")
        self.fernet = Fernet(key.encode())

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return self.fernet.encrypt(value.encode()).decode()

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return self.fernet.decrypt(value.encode()).decode()