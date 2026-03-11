import os
import base64
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

def derive_key(password: str, salt: bytes) -> bytes:
    """Derives a 32-byte key from password and salt."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=600000,
        backend=default_backend()
    )
    return kdf.derive(password.encode())

def encrypt_data_with_password(data: bytes, password: str) -> tuple[bytes, bytes, bytes, bytes]:
    """
    Encrypts data (e.g. keys) using a derived key from password.
    Returns (salt, nonce, ciphertext, tag).
    """
    salt = os.urandom(16)
    key = derive_key(password, salt)
    
    nonce = os.urandom(12)
    cipher = Cipher(algorithms.AES(key), modes.GCM(nonce), backend=default_backend())
    encryptor = cipher.encryptor()
    
    ciphertext = encryptor.update(data) + encryptor.finalize()
    return salt, nonce, ciphertext, encryptor.tag

def decrypt_data_with_password(salt: bytes, nonce: bytes, ciphertext: bytes, tag: bytes, password: str) -> bytes:
    """
    Decrypts data using derived key from password.
    """
    key = derive_key(password, salt)
    
    cipher = Cipher(algorithms.AES(key), modes.GCM(nonce, tag), backend=default_backend())
    decryptor = cipher.decryptor()
    
    return decryptor.update(ciphertext) + decryptor.finalize()
