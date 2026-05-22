from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from urllib.parse import urlparse, parse_qs
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

connect_args = {}
if DATABASE_URL:
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
    connect_args=connect_args
)

session_local = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

Base = declarative_base()

async def init_db():
    """Create all database tables on startup"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def get_db():
  async with session_local() as session:
    yield session