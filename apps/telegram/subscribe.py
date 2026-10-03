"""Administrator CLI for mapping a logistician to a Telegram chat."""

import argparse
import os
import re
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import create_engine, insert, select, update

from backend.infrastructure.postgres import models as db

CHAT_ID_PATTERN = re.compile(r"^-?[0-9]{1,20}$")


def normalize_chat_id(value: str) -> str:
    """Accept only a numeric Telegram chat identity."""
    if CHAT_ID_PATTERN.fullmatch(value) is None:
        raise ValueError("Invalid Telegram chat ID")
    return value


def set_subscription(database_url: str, user_id: UUID, chat_id: str, enabled: bool) -> None:
    """Enable or disable a logistician's delivery; the worker rechecks scope."""
    chat_id = normalize_chat_id(chat_id)
    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            role = connection.execute(
                select(db.users.c.role).where(db.users.c.id == user_id, db.users.c.is_active)
            ).scalar_one_or_none()
            if role != "logistician":
                raise ValueError("Active logistician account required")
            existing_ids = (
                connection.execute(
                    select(db.telegram_subscriptions.c.id)
                    .where(
                        db.telegram_subscriptions.c.user_id == user_id,
                        db.telegram_subscriptions.c.chat_id == chat_id,
                    )
                    .with_for_update()
                )
                .scalars()
                .all()
            )
            if existing_ids:
                connection.execute(
                    update(db.telegram_subscriptions)
                    .where(db.telegram_subscriptions.c.id.in_(existing_ids))
                    .values(enabled=enabled)
                )
            else:
                connection.execute(
                    insert(db.telegram_subscriptions).values(
                        id=uuid4(),
                        user_id=user_id,
                        chat_id=chat_id,
                        enabled=enabled,
                        created_at=datetime.now(timezone.utc),
                    )
                )
    finally:
        engine.dispose()


def main() -> None:
    """Run the subscription command using the configured database."""
    parser = argparse.ArgumentParser()
    parser.add_argument("user_id", type=UUID)
    parser.add_argument("chat_id")
    parser.add_argument("--disable", action="store_true")
    args = parser.parse_args()
    set_subscription(os.environ["DATABASE_URL"], args.user_id, args.chat_id, not args.disable)


if __name__ == "__main__":
    main()
