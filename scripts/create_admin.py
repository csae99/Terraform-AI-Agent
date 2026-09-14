"""
CLI Utility to Bootstrap and Manage Super-Admin Accounts for Terraform AI Agent.

Usage:
    # 1. Create a brand new super-admin account
    python scripts/create_admin.py --username admin --password "StrongPassword123!" --email admin@platform.io

    # 2. Promote an existing user to Super-Admin
    python scripts/create_admin.py --promote existing_user

    # 3. Demote a Super-Admin back to standard user
    python scripts/create_admin.py --demote existing_user

    # 4. List all users and their admin status
    python scripts/create_admin.py --list
"""

import os
import sys
import argparse

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from tools.project.tracker import UserTracker, UserModel, SessionLocal


def create_admin(username, password, email=None):
    session = SessionLocal()
    try:
        existing = session.query(UserModel).filter(UserModel.username == username).first()
        if existing:
            print(f"[!] User '{username}' already exists. Promoting to Super-Admin...")
            existing.is_superuser = True
            existing.status = "active"
            session.commit()
            print(f"[SUCCESS] User '{username}' is now a Super-Admin.")
            return True

        user = UserModel(username=username, email=email, is_superuser=True, status="active")
        user.set_password(password)
        session.add(user)
        session.commit()
        print(f"[SUCCESS] Super-Admin user '{username}' created successfully!")
        return True
    finally:
        session.close()


def promote_user(username):
    session = SessionLocal()
    try:
        user = session.query(UserModel).filter(UserModel.username == username).first()
        if not user:
            print(f"[ERROR] User '{username}' not found in database.")
            return False
        user.is_superuser = True
        session.commit()
        print(f"[SUCCESS] User '{username}' has been promoted to Super-Admin.")
        return True
    finally:
        session.close()


def demote_user(username):
    session = SessionLocal()
    try:
        user = session.query(UserModel).filter(UserModel.username == username).first()
        if not user:
            print(f"[ERROR] User '{username}' not found in database.")
            return False
        user.is_superuser = False
        session.commit()
        print(f"[SUCCESS] User '{username}' has been demoted to standard user.")
        return True
    finally:
        session.close()


def list_users():
    session = SessionLocal()
    try:
        users = session.query(UserModel).order_by(UserModel.id.asc()).all()
        print("\n" + "=" * 75)
        print(f"{'ID':<5} {'USERNAME':<20} {'ROLE':<15} {'STATUS':<12} {'CREATED AT':<20}")
        print("=" * 75)
        for u in users:
            role = "Super-Admin" if u.is_superuser else "Standard"
            status = getattr(u, "status", "active") or "active"
            created = u.created_at.strftime("%Y-%m-%d %H:%M") if u.created_at else "-"
            print(f"{u.id:<5} {u.username:<20} {role:<15} {status:<12} {created:<20}")
        print("=" * 75 + "\n")
    finally:
        session.close()


def main():
    parser = argparse.ArgumentParser(description="Manage Terraform AI Agent Super-Admin Accounts")
    parser.add_argument("--username", help="Username for new admin account")
    parser.add_argument("--password", help="Password for new admin account")
    parser.add_argument("--email", help="Email for new admin account", default=None)
    parser.add_argument("--promote", help="Promote an existing username to Super-Admin")
    parser.add_argument("--demote", help="Demote a Super-Admin to standard user")
    parser.add_argument("--list", action="store_true", help="List all users and their admin status")

    args = parser.parse_args()

    if args.list:
        list_users()
    elif args.promote:
        promote_user(args.promote)
    elif args.demote:
        demote_user(args.demote)
    elif args.username and args.password:
        create_admin(args.username, args.password, args.email)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
