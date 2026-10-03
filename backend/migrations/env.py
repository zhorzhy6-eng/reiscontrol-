"""Alembic environment; models and migrations are added in later stages."""

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = None


def database_url() -> str:
    """Read the database URL from the environment, never from the repository."""
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL must be set before running Alembic")
    return url


def run_migrations_offline() -> None:
    """Configure Alembic for SQL generation without a connection."""
    context.configure(url=database_url(), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Configure Alembic with a live PostgreSQL connection."""
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = database_url()
    engine = engine_from_config(configuration, prefix="sqlalchemy.", poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
