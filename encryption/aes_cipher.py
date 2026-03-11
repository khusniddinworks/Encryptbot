import os
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

def generate_aes_key():
    """Generates a random 256-bit AES key."""
    return os.urandom(32)

def encrypt_aes(data: bytes, key: bytes) -> tuple[bytes, bytes, bytes]:
    """
    Encrypts data using AES-256-GCM.
    Returns (nonce, ciphertext, tag).
    """
    nonce = os.urandom(12)
    cipher = Cipher(algorithms.AES(key), modes.GCM(nonce), backend=default_backend())
    encryptor = cipher.encryptor()
    
    ciphertext = encryptor.update(data) + encryptor.finalize()
    return nonce, ciphertext, encryptor.tag

def decrypt_aes(nonce: bytes, ciphertext: bytes, tag: bytes, key: bytes) -> bytes:
    """
    Decrypts data using AES-256-GCM.
    """
    cipher = Cipher(algorithms.AES(key), modes.GCM(nonce, tag), backend=default_backend())
    decryptor = cipher.decryptor()
    
    return decryptor.update(ciphertext) + decryptor.finalize()

# For large files, we should use streaming, but since current logic uses memory, 
# I'll keep it simple for now or implement a more robust version later.
