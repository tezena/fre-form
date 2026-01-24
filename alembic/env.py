import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# 1. Import your settings and models
from sqlmodel import SQLModel       # <--- Import from the library directly
from app.db import base             # <--- Import your base file so models register
from app.core.config import settings
# 2. Config object
config = context.config

# 3. Setup Logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 4. Set the Database URL (Use the Async one directly!)
# We do NOT replace +asyncpg with +psycopg2 here.
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# 5. Set Metadata
target_metadata = SQLModel.metadata

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """The sync function that runs the actual migration logic."""
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations in 'online' mode (Async version)."""
    
    # 6. Create the ASYNC Engine
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    # 7. Use the Async Connection
    async with connectable.connect() as connection:
        # 8. 'Run Sync' bridges the gap between Async engine and Sync Alembic internals
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())