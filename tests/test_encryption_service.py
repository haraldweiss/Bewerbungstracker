"""Tests für die Envelope-Encryption-Architektur (Salt + DEK + KEK)."""

import pytest
from cryptography.fernet import InvalidToken

from encryption_service import EncryptionService, SALT_BYTES, DEK_BYTES


def test_generate_salt_random_and_correct_length():
    a = EncryptionService.generate_salt()
    b = EncryptionService.generate_salt()
    assert isinstance(a, bytes)
    assert len(a) == SALT_BYTES
    assert a != b  # zufällig


def test_derive_kek_deterministic_for_same_inputs():
    salt = EncryptionService.generate_salt()
    k1 = EncryptionService.derive_kek("password123", salt)
    k2 = EncryptionService.derive_kek("password123", salt)
    assert k1 == k2


def test_derive_kek_different_for_different_salt():
    s1 = EncryptionService.generate_salt()
    s2 = EncryptionService.generate_salt()
    k1 = EncryptionService.derive_kek("password123", s1)
    k2 = EncryptionService.derive_kek("password123", s2)
    assert k1 != k2


def test_derive_kek_rejects_empty_password():
    salt = EncryptionService.generate_salt()
    with pytest.raises(ValueError):
        EncryptionService.derive_kek("", salt)


def test_derive_kek_rejects_invalid_salt():
    with pytest.raises(ValueError):
        EncryptionService.derive_kek("password", b"too_short")


def test_create_user_keys_roundtrip():
    salt, encrypted_dek, dek = EncryptionService.create_user_keys("hunter2")
    unlocked = EncryptionService.unlock_dek("hunter2", salt, encrypted_dek)
    assert unlocked == dek


def test_unlock_dek_fails_with_wrong_password():
    salt, encrypted_dek, _dek = EncryptionService.create_user_keys("correct")
    with pytest.raises(InvalidToken):
        EncryptionService.unlock_dek("wrong", salt, encrypted_dek)


def test_encrypt_decrypt_data_roundtrip():
    _salt, _enc_dek, dek = EncryptionService.create_user_keys("pw")
    cipher = EncryptionService.encrypt_data("hello world", dek)
    assert cipher != "hello world"
    assert EncryptionService.decrypt_data(cipher, dek) == "hello world"


def test_encrypt_data_nondeterministic_but_decrypts():
    _salt, _enc_dek, dek = EncryptionService.create_user_keys("pw")
    c1 = EncryptionService.encrypt_data("same", dek)
    c2 = EncryptionService.encrypt_data("same", dek)
    assert c1 != c2  # Fernet hat IV/Timestamp
    assert EncryptionService.decrypt_data(c1, dek) == "same"
    assert EncryptionService.decrypt_data(c2, dek) == "same"


def test_decrypt_with_different_dek_fails():
    _, _, dek1 = EncryptionService.create_user_keys("pw1")
    _, _, dek2 = EncryptionService.create_user_keys("pw2")
    cipher = EncryptionService.encrypt_data("secret", dek1)
    with pytest.raises(InvalidToken):
        EncryptionService.decrypt_data(cipher, dek2)


def test_password_change_preserves_dek():
    """Kernpunkt der Architektur: Passwort-Wechsel bricht keine Backups.

    Beim Re-Wrap bleibt der DEK identisch – mit altem DEK verschlüsselte Daten
    bleiben mit dem neuen Salt + neu-gewrappten DEK weiterhin entschlüsselbar.
    """
    salt, encrypted_dek, dek = EncryptionService.create_user_keys("oldpw")
    cipher = EncryptionService.encrypt_data("legacy backup", dek)

    new_salt, new_encrypted_dek = EncryptionService.rewrap_dek_for_new_password(
        old_password="oldpw",
        new_password="newpw",
        old_salt=salt,
        encrypted_dek=encrypted_dek,
    )
    assert new_salt != salt
    assert new_encrypted_dek != encrypted_dek

    # Der neue Wrap muss denselben DEK liefern → alte Backups bleiben lesbar
    new_dek = EncryptionService.unlock_dek("newpw", new_salt, new_encrypted_dek)
    assert new_dek == dek
    assert EncryptionService.decrypt_data(cipher, new_dek) == "legacy backup"


def test_password_change_old_password_no_longer_works():
    salt, encrypted_dek, _dek = EncryptionService.create_user_keys("oldpw")
    new_salt, new_encrypted_dek = EncryptionService.rewrap_dek_for_new_password(
        "oldpw", "newpw", salt, encrypted_dek
    )
    with pytest.raises(InvalidToken):
        EncryptionService.unlock_dek("oldpw", new_salt, new_encrypted_dek)
