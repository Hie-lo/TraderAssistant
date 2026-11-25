from typing import AsyncGenerator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession, AsyncConnection
from app.core.config import settings
from app.core.logger import logger

# Configure async engine
# Note: pool_pre_ping checks connectivity before checking out a connection
connect_args = {}
if "sqlite" in settings.DATABASE_URL:
    connect_args["check_same_thread"] = False

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
    pool_pre_ping=True,
    connect_args=connect_args
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Mandatory to prevent MissingGreenlet in SQLAlchemy 2.0
    autoflush=False
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for yielding an async database session per request."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def ensure_schema_columns(conn: AsyncConnection) -> None:
    """Idempotently adds new columns on existing databases where create_all does not alter tables."""
    if engine.dialect.name == "postgresql":
        await conn.execute(text("ALTER TABLE trades ADD COLUMN IF NOT EXISTS telegram_message_id INTEGER"))
        await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_end_date TIMESTAMPTZ"))
    else:
        trade_cols = (await conn.execute(text("PRAGMA table_info(trades)"))).fetchall()
        if trade_cols and not any(c[1] == "telegram_message_id" for c in trade_cols):
            await conn.execute(text("ALTER TABLE trades ADD COLUMN telegram_message_id INTEGER"))
        user_cols = (await conn.execute(text("PRAGMA table_info(users)"))).fetchall()
        if user_cols and not any(c[1] == "subscription_end_date" for c in user_cols):
            await conn.execute(text("ALTER TABLE users ADD COLUMN subscription_end_date DATETIME"))
