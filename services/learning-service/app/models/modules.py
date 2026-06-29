from datetime import datetime
from enum import Enum

from sqlalchemy import BigInteger, ForeignKey, DateTime, Enum as SqlEnum, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.common import enum_values


class ModuleStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class Module(Base):
    __tablename__ = "modules"
    __table_args__ = (
        UniqueConstraint(
            "learning_path_id",
            "sort_order",
            name="uq_modules_path_sort_order",
        ),
    )

    # mapped_column maps each Python attribute to a concrete column
    module_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True, 
        autoincrement=True
    )
    learning_path_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("learning_paths.learning_path_id", ondelete="CASCADE"),
        nullable=False
    )
    title: Mapped[str] = mapped_column(
        String(200), 
        nullable=False
    )
    description: Mapped[str | None] = mapped_column(
        Text, 
        nullable=True
    )
    content: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    sort_order: Mapped[int] = mapped_column(
        nullable=False
    )
    estimated_minutes: Mapped[int | None] = mapped_column(
        nullable=True
    )
    status: Mapped[ModuleStatus] = mapped_column(
        SqlEnum(ModuleStatus, values_callable=enum_values),
        nullable=False,
        default=ModuleStatus.DRAFT,
        server_default=ModuleStatus.DRAFT.value,
    )
    visible_to_class_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )


    # relationships
    learning_path = relationship(
        "LearningPath",
        foreign_keys="Module.learning_path_id",
        back_populates="modules",
    )
    materials = relationship(
        "ModuleMaterial",
        foreign_keys="ModuleMaterial.module_id",
        back_populates="module",
        cascade="all, delete-orphan",
    )
    progress_records = relationship(
        "ModuleProgress",
        foreign_keys="ModuleProgress.module_id",
        back_populates="module",
        cascade="all, delete-orphan",
    )
    prerequisite_rule = relationship(
        "ModulePrerequisite",
        foreign_keys="ModulePrerequisite.module_id",
        back_populates="module",
        cascade="all, delete-orphan",
        uselist=False,
    )
    quiz = relationship(
        "Quiz",
        foreign_keys="Quiz.module_id",
        back_populates="module",
        cascade="all, delete-orphan",
        uselist=False,
    )
    short_answer_assessment = relationship(
        "ShortAnswerAssessment",
        foreign_keys="ShortAnswerAssessment.module_id",
        back_populates="module",
        cascade="all, delete-orphan",
        uselist=False,
    )
