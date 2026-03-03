import os
import hashlib
import logging
import base64
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class SecurityManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_ciphers()
        return cls._instance

    def _init_ciphers(self):
        raw_key = os.getenv("ENCRYPTION_KEY")
        if not raw_key:
            # Fallback only for non-critical paths or dev
            logger.warning("⚠️ WARNING: ENCRYPTION_KEY not found in .env. Encryption will fail.")
            self.direct_cipher = None
            self.derived_cipher = None
            return

        # 1. Direct Fernet (Standard for App & New Credentials)
        #    Accept either a valid Fernet key (44-char base64url) or any raw string
        #    (hex, passphrase, etc.) — in the latter case, derive a proper key via SHA-256.
        try:
            self.direct_cipher = Fernet(raw_key.encode())
            logger.info("✅ Direct Fernet key loaded from ENCRYPTION_KEY")
        except Exception:
            # Raw key isn't valid base64url Fernet — derive one deterministically
            try:
                key_bytes = hashlib.sha256(raw_key.encode()).digest()
                fernet_key = base64.urlsafe_b64encode(key_bytes)
                self.direct_cipher = Fernet(fernet_key)
                logger.info("✅ Fernet key derived from ENCRYPTION_KEY via SHA-256")
            except Exception as e:
                logger.error(f"❌ Direct Key Init Failed even after derivation: {e}")
                self.direct_cipher = None

        # 2. Derived Key (Legacy/Scraper Compatibility)
        try:
            derived_salt = os.getenv("DERIVED_KEY_SALT", "").encode() or b'fallback_salt_change_me'
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=derived_salt,
                iterations=100000,
                backend=default_backend()
            )
            derived_key = base64.urlsafe_b64encode(kdf.derive(raw_key.encode()))
            self.derived_cipher = Fernet(derived_key)
        except Exception as e:
             logger.warning(f"⚠️ Derived Key Init Failed: {e}")
             self.derived_cipher = None

    def encrypt(self, text):
        """Encrypts using the Standard (Direct) method. Returns bytes."""
        if not text: return None
        if not self.direct_cipher:
            raise RuntimeError("Encryption unavailable: check ENCRYPTION_KEY")
        return self.direct_cipher.encrypt(text.encode())

    def decrypt(self, data):
        """Auto-detects encryption mode by trying Direct then Derived."""
        if not data: return ""
        
        # Normalize input to bytes
        if isinstance(data, str): data = data.encode()
        if isinstance(data, memoryview): data = data.tobytes()

        # Strategy 1: Direct (App Standard)
        if self.direct_cipher:
            try:
                return self.direct_cipher.decrypt(data).decode()
            except InvalidToken:
                logger.debug("Direct decryption failed, trying derived key")
            except Exception as e:
                logger.warning(f"⚠️ Unexpected error in direct decryption: {e}")

        # Strategy 2: Derived (Legacy Scrapers)
        if self.derived_cipher:
            try:
                return self.derived_cipher.decrypt(data).decode()
            except InvalidToken:
                logger.debug("Derived decryption also failed")
            except Exception as e:
                logger.warning(f"⚠️ Unexpected error in derived decryption: {e}")
        
        logger.error("❌ All decryption strategies failed")
        return "[Error Decrypt]"

# Singleton Access
_manager = SecurityManager()

def cifrar(dato):
    """Interfaz compatible con security.py anterior"""
    return _manager.encrypt(dato)

def descifrar(dato_cifrado):
    """Interfaz compatible con security.py y encriptacion.py"""
    return _manager.decrypt(dato_cifrado)

def generar_hash_dni(dni):
    """Crea un hash irreversible para búsquedas rápidas (Blind Index)."""
    if not dni: return None
    salt = os.getenv("DNI_HASH_SALT", "")
    if not salt:
        logger.warning("⚠️ DNI_HASH_SALT not set in .env — using empty salt (insecure)")
    return hashlib.sha256((dni + salt).encode()).hexdigest()