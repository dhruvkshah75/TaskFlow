from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from .config import settings
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

SQLALCHEMY_DATABASE_URL = str(settings.DATABASE_URL)

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_pre_ping=True  # Checks connection health before query
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

ASYNC_DATABASE_URL = SQLALCHEMY_DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")

# Create the Async Engine connecting to the same database
async_engine = create_async_engine(
    ASYNC_DATABASE_URL, 
    echo=False,
    pool_pre_ping=True,  #Checks connection health before query
    connect_args={
        "prepare_threshold": None # disable prepared statements(Required for PgBouncer)
    }
)

# Create the async session factory
AsyncSessionLocal = async_sessionmaker(
    async_engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)