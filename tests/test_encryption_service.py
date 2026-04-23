"""Tests for EncryptionService with per-user PBKDF2 key derivation"""

import pytest
from encryption_service import EncryptionService


def test_derive_encryption_key_from_user():
    """Test that same user email+password gets same encryption key"""
    email = "test@example.com"
    password = "secure_password_123"

    key1 = EncryptionService.derive_user_key(email, password)
    key2 = EncryptionService.derive_user_key(email, password)

    # Same user should get same key (deterministic)
    assert key1 == key2
    assert isinstance(key1, bytes)
    assert len(key1) > 0


def test_different_users_get_different_keys():
    """Test that different users get different encryption keys"""
    password = "same_password_123"

    key1 = EncryptionService.derive_user_key("user1@example.com", password)
    key2 = EncryptionService.derive_user_key("user2@example.com", password)

    # Different users should get different keys
    assert key1 != key2


def test_encrypt_decrypt_user_data():
    """Test roundtrip encryption and decryption"""
    email = "test@example.com"
    password = "secure_password_123"
    plaintext = "This is sensitive user data"

    # Derive key
    key = EncryptionService.derive_user_key(email, password)

    # Encrypt
    encrypted = EncryptionService.encrypt_data(plaintext, key)
    assert isinstance(encrypted, str)
    assert encrypted != plaintext

    # Decrypt
    decrypted = EncryptionService.decrypt_data(encrypted, key)
    assert decrypted == plaintext


def test_encrypt_multiple_messages_different_ciphertexts():
    """Test that encrypting same plaintext twice produces different ciphertexts (Fernet includes timestamp)"""
    email = "test@example.com"
    password = "secure_password_123"
    plaintext = "Same data"

    key = EncryptionService.derive_user_key(email, password)

    encrypted1 = EncryptionService.encrypt_data(plaintext, key)
    encrypted2 = EncryptionService.encrypt_data(plaintext, key)

    # Fernet includes timestamp, so ciphertexts differ
    assert encrypted1 != encrypted2

    # But both decrypt to same plaintext
    assert EncryptionService.decrypt_data(encrypted1, key) == plaintext
    assert EncryptionService.decrypt_data(encrypted2, key) == plaintext


def test_wrong_key_fails_decryption():
    """Test that decrypting with wrong key fails"""
    email1 = "user1@example.com"
    email2 = "user2@example.com"
    password = "same_password_123"
    plaintext = "Secret message"

    key1 = EncryptionService.derive_user_key(email1, password)
    key2 = EncryptionService.derive_user_key(email2, password)

    encrypted = EncryptionService.encrypt_data(plaintext, key1)

    # Should fail with wrong key
    with pytest.raises(Exception):
        EncryptionService.decrypt_data(encrypted, key2)


def test_encrypt_empty_string():
    """Test encryption of empty string"""
    email = "test@example.com"
    password = "password"

    key = EncryptionService.derive_user_key(email, password)

    encrypted = EncryptionService.encrypt_data("", key)
    decrypted = EncryptionService.decrypt_data(encrypted, key)

    assert decrypted == ""


def test_encrypt_large_data():
    """Test encryption of large data"""
    email = "test@example.com"
    password = "password"
    plaintext = "x" * 10000  # 10KB of data

    key = EncryptionService.derive_user_key(email, password)

    encrypted = EncryptionService.encrypt_data(plaintext, key)
    decrypted = EncryptionService.decrypt_data(encrypted, key)

    assert decrypted == plaintext
