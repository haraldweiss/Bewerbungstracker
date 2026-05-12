#!/usr/bin/env python3
import sys
import os

os.chdir('/Library/WebServer/Documents/Bewerbungstracker')
sys.path.insert(0, '.')

from app import create_app
from database import db
from models import User

app = create_app()

with app.app_context():
    user = User.query.filter_by(email='harald.weiss@wolfinisoftware.de').first()
    
    if not user:
        print("❌ User nicht gefunden")
        sys.exit(1)
    
    print(f"User: {user.email}")
    print(f"  is_admin: {user.is_admin}")
    print(f"  is_active: {user.is_active}")
    print(f"  email_confirmed: {user.email_confirmed}")
    
    user.is_active = True
    user.is_admin = True
    user.email_confirmed = True
    
    db.session.commit()
    
    print(f"\n✓ User genehmigt und als Admin gesetzt!")
