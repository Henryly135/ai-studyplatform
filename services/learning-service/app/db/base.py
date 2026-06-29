"""SQLAlchemy declarative base for future ORM models."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Common base class that all ORM models should inherit from."""
    pass
