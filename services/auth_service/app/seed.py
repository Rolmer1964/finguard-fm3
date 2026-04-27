import logging

from sqlalchemy import select

from .db import SessionLocal
from .jwt_utils import hash_password
from .models import User
from .settings import settings

logger = logging.getLogger("auth.seed")


def seed_admin() -> None:
    with SessionLocal() as db:
        exists = db.execute(select(User).where(User.email == settings.ADMIN_EMAIL)).scalar_one_or_none()
        if exists:
            logger.info("admin already exists: %s", settings.ADMIN_EMAIL)
            return
        user = User(
            email=settings.ADMIN_EMAIL,
            name=settings.ADMIN_NAME,
            password_hash=hash_password(settings.ADMIN_PASSWORD),
            role="admin",
        )
        db.add(user)
        db.commit()
        logger.info("admin user created: %s", settings.ADMIN_EMAIL)
