"""Encryption service: Envelope Encryption (DEK + KEK).

Architektur:
- Jeder User bekommt einen zufälligen Data Encryption Key (DEK, 32 Bytes), der
  effektiv die Daten verschlüsselt.
- Der DEK wird mit einem aus dem Passwort abgeleiteten Key Encryption Key (KEK)
  verschlüsselt und so im User-Record persistiert (`encrypted_data_key`).
- Die Ableitung des KEK nutzt einen pro-User zufälligen Salt
  (`encryption_salt`) → kein gemeinsamer Brute-Force-Vektor.
- Bei Passwort-Änderung wird NUR der KEK neu abgeleitet und der DEK damit neu
  verschlüsselt – der DEK selbst bleibt stabil → vorhandene Backups
  bleiben entschlüsselbar.
"""

import base64
import os
from typing import Tuple
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

SALT_BYTES = 16
DEK_BYTES = 32
PBKDF2_ITERATIONS = 600_000  # OWASP 2023 für SHA-256


class EncryptionService:
    """Envelope Encryption Service – DEK/KEK-Pattern."""

    @staticmethod
    def generate_salt() -> bytes:
        """Zufälliger 16-Byte Salt für PBKDF2 (pro User)."""
        return os.urandom(SALT_BYTES)

    @staticmethod
    def generate_dek() -> bytes:
        """Generiert einen neuen Data Encryption Key (Fernet-Format)."""
        return Fernet.generate_key()

    @staticmethod
    def derive_kek(password: str, salt: bytes) -> bytes:
        """Leitet den Key Encryption Key aus Passwort + per-User-Salt ab."""
        if not password:
            raise ValueError("Passwort darf nicht leer sein")
        if not salt or len(salt) != SALT_BYTES:
            raise ValueError(f"Salt muss {SALT_BYTES} Bytes sein")

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=PBKDF2_ITERATIONS,
        )
        derived = kdf.derive(password.encode('utf-8'))
        return base64.urlsafe_b64encode(derived)

    @staticmethod
    def wrap_dek(dek: bytes, kek: bytes) -> str:
        """Verschlüsselt den DEK mit dem KEK (Wrapping)."""
        cipher = Fernet(kek)
        return cipher.encrypt(dek).decode('utf-8')

    @staticmethod
    def unwrap_dek(wrapped_dek: str, kek: bytes) -> bytes:
        """Entschlüsselt den DEK mit dem KEK (Unwrapping)."""
        cipher = Fernet(kek)
        return cipher.decrypt(wrapped_dek.encode('utf-8'))

    @staticmethod
    def encrypt_data(plaintext: str, dek: bytes) -> str:
        """Verschlüsselt Klartext mit dem DEK."""
        cipher = Fernet(dek)
        return cipher.encrypt(plaintext.encode('utf-8')).decode('utf-8')

    @staticmethod
    def decrypt_data(encrypted: str, dek: bytes) -> str:
        """Entschlüsselt Daten mit dem DEK."""
        cipher = Fernet(dek)
        return cipher.decrypt(encrypted.encode('utf-8')).decode('utf-8')

    # ── Convenience für User-Onboarding ───────────────────────────────────

    @staticmethod
    def create_user_keys(password: str) -> Tuple[bytes, str, bytes]:
        """Generiert Salt + DEK + verschlüsselten DEK für einen neuen User.

        Returns:
            (salt, encrypted_data_key, dek) – Salt + Wrapped DEK persistieren,
            DEK in den KeyCache legen.
        """
        salt = EncryptionService.generate_salt()
        dek = EncryptionService.generate_dek()
        kek = EncryptionService.derive_kek(password, salt)
        encrypted_dek = EncryptionService.wrap_dek(dek, kek)
        return salt, encrypted_dek, dek

    @staticmethod
    def unlock_dek(password: str, salt: bytes, encrypted_dek: str) -> bytes:
        """Entsperrt den DEK eines Users beim Login."""
        kek = EncryptionService.derive_kek(password, salt)
        return EncryptionService.unwrap_dek(encrypted_dek, kek)

    @staticmethod
    def rewrap_dek_for_new_password(
        old_password: str,
        new_password: str,
        old_salt: bytes,
        encrypted_dek: str,
    ) -> Tuple[bytes, str]:
        """Verschlüsselt den DEK mit neuem Passwort neu (Password-Change-Flow).

        Der DEK selbst bleibt unverändert – existierende Backups bleiben gültig.
        Returns: (new_salt, new_encrypted_dek)
        """
        old_kek = EncryptionService.derive_kek(old_password, old_salt)
        dek = EncryptionService.unwrap_dek(encrypted_dek, old_kek)
        new_salt = EncryptionService.generate_salt()
        new_kek = EncryptionService.derive_kek(new_password, new_salt)
        new_encrypted_dek = EncryptionService.wrap_dek(dek, new_kek)
        return new_salt, new_encrypted_dek
