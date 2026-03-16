"""
Database Connection Management — Central persistence layer for Review Prep Engine.

Provides:
- SQLite connection pooling with connection reuse
- Session management for atomic transactions
- Health check utilities
- Graceful error handling and connection recovery
"""

import logging
import os
from contextlib import contextmanager
from typing import Optional

try:
    from sqlalchemy import create_engine, text, pool
    from sqlalchemy.orm import sessionmaker, Session
    from sqlalchemy.pool import QueuePool, StaticPool
    HAS_SQLALCHEMY = True
except ImportError:
    HAS_SQLALCHEMY = False

logger = logging.getLogger(__name__)

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./review_prep.db")

# SQLAlchemy engine with connection pooling
# For SQLite, we use StaticPool for in-memory or local file databases
# pool_pre_ping=True: test connections before using them
engine = None
SessionFactory = None

if HAS_SQLALCHEMY:
    if "sqlite:///" in DATABASE_URL:
        # SQLite configuration (local file)
        engine = create_engine(
            DATABASE_URL,
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
            echo=False,
        )
    else:
        # PostgreSQL or other database
        engine = create_engine(
            DATABASE_URL,
            poolclass=QueuePool,
            pool_size=10,
            max_overflow=5,
            pool_timeout=30,
            pool_recycle=3600,
            pool_pre_ping=True,
            echo=False,
        )

    SessionFactory = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)
    logger.info("Database engine initialized: %s", DATABASE_URL)
else:
    logger.warning("SQLAlchemy not installed; database layer unavailable")


@contextmanager
def get_session():
    """
    Context manager for database sessions.

    Usage:
        with get_session() as session:
            result = session.query(...).first()
            # Auto-commits on success, rolls back on exception
    """
    if not SessionFactory:
        raise RuntimeError("Database session factory not initialized")

    session = SessionFactory()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error("Database transaction failed: %s", str(e))
        raise
    finally:
        session.close()


def check_database() -> bool:
    """Check database connectivity."""
    if not engine:
        logger.warning("Database engine not initialized")
        return False

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        logger.debug("Database health check passed")
        return True
    except Exception as e:
        logger.error("Database health check failed: %s", str(e))
        return False


async def shutdown():
    """Shutdown database connections."""
    if engine:
        try:
            engine.dispose()
            logger.info("Database connection pool disposed")
        except Exception as e:
            logger.error("Error disposing database pool: %s", str(e))
