from cryptography.fernet import Fernet
import os


class IMAPCredentialManager:
    """Service for encrypting/decrypting IMAP credentials"""

    @staticmethod
    def _get_cipher():
        """Get Fernet cipher from env"""
        encryption_key = os.getenv('ENCRYPTION_KEY')
        if not encryption_key:
            raise ValueError("ENCRYPTION_KEY environment variable not set")
        return Fernet(encryption_key.encode())

    @staticmethod
    def encrypt_password(password: str) -> str:
        """Encrypt IMAP password"""
        cipher = IMAPCredentialManager._get_cipher()
        encrypted = cipher.encrypt(password.encode())
        return encrypted.decode('utf-8')

    @staticmethod
    def decrypt_password(encrypted_password: str) -> str:
        """Decrypt IMAP password"""
        cipher = IMAPCredentialManager._get_cipher()
        decrypted = cipher.decrypt(encrypted_password.encode())
        return decrypted.decode('utf-8')
