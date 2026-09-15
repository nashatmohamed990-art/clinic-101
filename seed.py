"""Seed script: create initial users and optionally sample data.
Run: python seed.py

Generates a strong random password for each account (instead of a
guessable default) and prints them once. Write them down / share them
with the doctor securely — they are not stored anywhere in plain text.
"""
import sys
import os
import secrets
import string

sys.path.insert(0, os.path.dirname(__file__))

from app import create_app, db
from app.models import User
from werkzeug.security import generate_password_hash

app = create_app()


def generate_password(length=12):
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


with app.app_context():
    # Create tables
    db.create_all()
    print("Tables created.")

    created_credentials = []

    # Create doctor account
    doctor = User.query.filter_by(username='doctor').first()
    if not doctor:
        pwd = generate_password()
        doctor = User(
            username='doctor',
            password_hash=generate_password_hash(pwd),
            full_name='Dr. Hisham',
            role='doctor',
            active=True
        )
        db.session.add(doctor)
        created_credentials.append(('doctor', pwd))
        print("Doctor account created.")
    else:
        print("Doctor account already exists.")

    # Create assistant accounts
    assistants = [
        ('assistant1', 'Assistant 1'),
        ('assistant2', 'Assistant 2'),
    ]
    for uname, fname in assistants:
        a = User.query.filter_by(username=uname).first()
        if not a:
            pwd = generate_password()
            a = User(
                username=uname,
                password_hash=generate_password_hash(pwd),
                full_name=fname,
                role='assistant',
                active=True
            )
            db.session.add(a)
            created_credentials.append((uname, pwd))
            print(f"Assistant account '{uname}' created.")
        else:
            print(f"Assistant '{uname}' already exists.")

    db.session.commit()
    print("\nDone! You can now run the application.")

    if created_credentials:
        print("\n" + "=" * 50)
        print("SAVE THESE CREDENTIALS NOW — they will not be shown again:")
        print("=" * 50)
        for username, pwd in created_credentials:
            print(f"  Username: {username}    Password: {pwd}")
        print("=" * 50)
        print("Everyone should change their password after first login")
        print("(top-right menu -> Password / كلمة المرور).")
    else:
        print("\nNo new accounts were created — all usernames already existed.")
