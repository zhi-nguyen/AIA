"""
crypto_service.py - Dịch vụ mã hóa giải mã
Sử dụng Fernet để mã hóa token trước khi lưu vào DB.
"""

from cryptography.fernet import Fernet
from config import get_settings

def get_fernet() -> Fernet:
    settings = get_settings()
    key = settings.encryption_key.encode('utf-8')
    # Fernet yêu cầu key 32 bytes base64-encoded. Nếu key không hợp lệ, ta có thể tự động padding hoặc hash.
    # Tuy nhiên, giả định encryption_key đã là 1 valid url-safe base64-encoded 32-byte key.
    # Nhưng để an toàn trong lúc dev, ta có thể sinh ra key hợp lệ nếu thiếu.
    try:
        return Fernet(key)
    except ValueError:
        import base64
        import hashlib
        # Tạo 32 bytes key từ chuỗi bất kỳ bằng SHA-256
        hashed = hashlib.sha256(key).digest()
        safe_key = base64.urlsafe_b64encode(hashed)
        return Fernet(safe_key)

def encrypt_token(token: str) -> str:
    if not token:
        return ""
    f = get_fernet()
    return f.encrypt(token.encode('utf-8')).decode('utf-8')

def decrypt_token(encrypted_token: str) -> str:
    if not encrypted_token:
        return ""
    f = get_fernet()
    return f.decrypt(encrypted_token.encode('utf-8')).decode('utf-8')
