"""
Script to create the first Super Admin user.
Run this after setting up the database and running migrations.

Usage:
    python scripts/create_super_admin.py
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

# ---------------------------------------------------------
# IMPORT ALL MODELS HERE TO REGISTER THEM
# ---------------------------------------------------------
from app.models.user import User, UserRole
from app.models.department import Department  # <--- ADD THIS
from app.models.student import Student        # <--- OPTIONAL BUT SAFER
# ---------------------------------------------------------

from app.db.session import async_engine
from app.core.security import get_password_hash

async def create_super_admin():
    """Create the first Super Admin user."""
    async_session = sessionmaker(
        async_engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        # Check if any Super Admin exists
        result = await session.execute(
            select(User).where(User.role == UserRole.SUPER_ADMIN)
        )
        existing_super_admin = result.scalar_one_or_none()

        if existing_super_admin:
            print("A Super Admin already exists in the database.")
            return

        # Get user input
        print("Creating the first Super Admin user...")
        email = input("Enter email: ").strip()
        password = input("Enter password: ").strip()
        full_name = input("Enter full name: ").strip()

        if not all([email, password, full_name]):
            print("Error: All fields are required.")
            return

        # Check if email already exists
        result = await session.execute(
            select(User).where(User.email == email)
        )
        existing_user = result.scalar_one_or_none()
        if existing_user:
            print(f"Error: User with email {email} already exists.")
            return

        # Create Super Admin
        super_admin = User(
            email=email,
            password_hash=get_password_hash(password),
            full_name=full_name,
            role=UserRole.SUPER_ADMIN,
            is_active=True,
        )

        session.add(super_admin)
        await session.commit()
        print(f"Super Admin created successfully: {email}")


if __name__ == "__main__":
    asyncio.run(create_super_admin())

