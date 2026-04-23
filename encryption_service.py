"""Encryption service for user data using per-user PBKDF2 key derivation"""

import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


class EncryptionService:
    """
    User-based encryption service using PBKDF2-HMAC-SHA256 for key derivation
    and Fernet (AES128-CBC + HMAC-SHA256) for symmetric encryption.

    Each user gets a unique encryption key derived from their email and password.
    Same user always gets the same key, different users get different keys.
    """

    SALT = b'bewerbungstracker_user_encryption'
    ITERATIONS = 100000

    @staticmethod
    def derive_user_key(email: str, password: str) -> bytes:
        """
        Derive a unique encryption key for a user based on their email and password.

        Args:
            email: User's email address
            password: User's password

        Returns:
            Base64-encoded Fernet key as bytes
        """
        # Combine email and password as the input material
        user_material = f"{email}:{password}".encode('utf-8')

        # Derive key using PBKDF2-HMAC-SHA256
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,  # 256 bits for Fernet key
            salt=EncryptionService.SALT,
            iterations=EncryptionService.ITERATIONS,
        )
        derived_key = kdf.derive(user_material)

        # Convert to base64-encoded Fernet key
        fernet_key = base64.urlsafe_b64encode(derived_key)
        return fernet_key

    @staticmethod
    def encrypt_data(plaintext: str, key: bytes) -> str:
        """
        Encrypt plaintext data using Fernet symmetric encryption.

        Args:
            plaintext: The data to encrypt
            key: Base64-encoded Fernet key from derive_user_key()

        Returns:
            Base64-encoded encrypted data as string
        """
        cipher = Fernet(key)
        plaintext_bytes = plaintext.encode('utf-8')
        encrypted_bytes = cipher.encrypt(plaintext_bytes)

        # Return as string (base64 encoded by Fernet)
        return encrypted_bytes.decode('utf-8')

    @staticmethod
    def decrypt_data(encrypted: str, key: bytes) -> str:
        """
        Decrypt Fernet-encrypted data.

        Args:
            encrypted: Base64-encoded encrypted data from encrypt_data()
            key: Base64-encoded Fernet key from derive_user_key()

        Returns:
            Decrypted plaintext string

        Raises:
            cryptography.fernet.InvalidToken: If decryption fails (wrong key, tampered data)
        """
        cipher = Fernet(key)
        encrypted_bytes = encrypted.encode('utf-8')
        decrypted_bytes = cipher.decrypt(encrypted_bytes)

        # Return as string
        return decrypted_bytes.decode('utf-8')
