#!/usr/bin/env python3
"""
Admin Promotion Script
Promotes a user to admin status by email address.

Usage:
    python scripts/promote_admin.py <email>
    python scripts/promote_admin.py harald.weiss@wolfinisoftware.de
"""

import sys
import os
from pathlib import Path

# Add parent directory to path so we can import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from app import create_app
from database import db
from models import User

# Load environment variables
load_dotenv()


def promote_admin(email: str) -> bool:
    """
    Promote a user to admin status.

    Args:
        email: User email address

    Returns:
        True if successful, False otherwise
    """
    app = create_app()

    with app.app_context():
        # Query user by email
        user = User.query.filter_by(email=email).first()

        if not user:
            print(f"✗ User not found: {email}")
            return False

        # Check if already admin
        if user.is_admin:
            print(f"⚠ User is already admin: {email}")
            return True

        # Set admin status
        try:
            user.is_admin = True
            db.session.commit()
            print(f"✓ User {email} promoted to admin")
            return True
        except Exception as e:
            db.session.rollback()
            print(f"✗ Database error: {str(e)}")
            return False


def main():
    """Main entry point"""
    # Check for email argument
    if len(sys.argv) < 2:
        print("Usage: python scripts/promote_admin.py <email>")
        print("Example: python scripts/promote_admin.py user@example.com")
        sys.exit(1)

    email = sys.argv[1]

    # Validate email format
    if '@' not in email or '.' not in email:
        print(f"✗ Invalid email format: {email}")
        sys.exit(1)

    # Promote user
    success = promote_admin(email)

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
