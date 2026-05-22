from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import NullPool
from urllib.parse import urlparse, parse_qs
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable not set")

connect_args = {
    "timeout": 10,
    "command_timeout": 10,
    "max_cached_statement_lifetime": 300,
    "max_cacheable_statement_size": 15_000,
}

parsed = urlparse(DATABASE_URL)
params = parse_qs(parsed.query)

if "sslmode" in params and params["sslmode"][0] == "require":
    connect_args["ssl"] = "require"

if "channel_binding" in params:
    connect_args["server_settings"] = {"jit": "off"}

DATABASE_URL = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

engine = create_async_engine(
    DATABASE_URL,
    echo=True,
    connect_args=connect_args,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

session_local = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

Base = declarative_base()

async def init_db():
    """Create all database tables on startup and handle schema migrations"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
        # Add missing columns to telemetry_events if they don't exist
        from sqlalchemy import text
        try:
            await conn.execute(text("""
                ALTER TABLE telemetry_events 
                ADD COLUMN IF NOT EXISTS ax FLOAT DEFAULT 0.0
            """))
        except Exception as e:
            print(f"Note: Could not add ax column: {e}")
            
        try:
            await conn.execute(text("""
                ALTER TABLE telemetry_events 
                ADD COLUMN IF NOT EXISTS ay FLOAT DEFAULT 0.0
            """))
        except Exception as e:
            print(f"Note: Could not add ay column: {e}")
            
        try:
            await conn.execute(text("""
                ALTER TABLE telemetry_events 
                ADD COLUMN IF NOT EXISTS az FLOAT DEFAULT 0.0
            """))
        except Exception as e:
            print(f"Note: Could not add az column: {e}")

async def get_db():
  async with session_local() as session:
    yield session