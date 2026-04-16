from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import create_engine, event
from app.core.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_size=10,
    max_overflow=20,
)

@event.listens_for(engine.sync_engine, "connect")
def on_connect(dbapi_conn, connection_record):
    from pgvector.asyncpg import register_vector
    import asyncio
    asyncio.get_event_loop().run_until_complete(register_vector(dbapi_conn))

sync_engine = create_engine(settings.DATABASE_URL_SYNC)

AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()