"""SQLAlchemy declarative base for AI service ORM models."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Common base class that all AI service ORM models inherit from."""

