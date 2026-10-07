import os
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.core.config import settings
from app.core.logging import logger
from app.database.base import Base

# Select DB URL based on test flag or environment
db_url = settings.SQLITE_TEST_DB if settings.USE_SQLITE_TEST else settings.DATABASE_URL

connect_args = {}
if db_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

try:
    engine = create_engine(db_url, connect_args=connect_args, echo=settings.DEBUG)
except Exception as e:
    logger.warning(f"Failed to initialize engine for {db_url}: {e}. Falling back to SQLite for development.")
    engine = create_engine(settings.SQLITE_TEST_DB, connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    """Creates database tables if they do not exist."""
    try:
        # Ensure all models are imported so they register with Base.metadata
        import app.models  # noqa: F401
        Base.metadata.create_all(bind=engine)
        logger.info("Database schema initialized successfully.")
    except Exception as e:
        logger.error(f"Database initialization error: {e}")



def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that provides a transactional SQLAlchemy session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
