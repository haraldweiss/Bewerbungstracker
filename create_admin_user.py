#!/usr/bin/env python3
import sys
import os
import secrets

os.chdir('/Library/WebServer/Documents/Bewerbungstracker')
sys.path.insert(0, '.')

from app import create_app
from database import db
from models import User
from auth_service import AuthService
from encryption_service import EncryptionService

app = create_app()

with app.app_context():
    email = 'anubclaw@gmail.com'
    password = secrets.token_urlsafe(16)
    
    # Check if user exists
    existing = User.query.filter_by(email=email).first()
    if existing:
        print(f"❌ User {email} existiert bereits")
        sys.exit(1)
    
    # Hash password
    password_hash = AuthService.hash_password(password)
    
    # Create Envelope-Encryption (salt + encrypted DEK)
    salt, encrypted_dek, _ = EncryptionService.create_user_keys(password)
    
    # Create user
    user = User(
        email=email,
        password_hash=password_hash,
        is_admin=True,
        is_active=True,
        email_confirmed=True,
        encryption_salt=salt,
        encrypted_data_key=encrypted_dek
    )
    
    db.session.add(user)
    db.session.commit()
    
    print(f"✓ Admin-User erstellt!")
    print(f"  Email: {email}")
    print(f"  Password: {password}")
    print()
    print("⚠️  Speichere dieses Passwort sicher!")
