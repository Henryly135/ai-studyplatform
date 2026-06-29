from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ModulePrerequisite(Base):
    __tablename__ = "module_prerequisites"
    __table_args__ = (
        UniqueConstraint("module_id", name="uq_module_prerequisites_module_id"),
        UniqueConstraint(
            "prerequisite_module_id",
            "module_id",
            name="uq_module_prerequisites_pair",
        ),
    )

    module_prerequisite_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )
    module_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("modules.module_id", ondelete="CASCADE"),
        nullable=False,
    )
    prerequisite_module_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("modules.module_id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
    )

    module = relationship(
        "Module",
        foreign_keys="ModulePrerequisite.module_id",
        back_populates="prerequisite_rule",
    )
    prerequisite_module = relationship(
        "Module",
        foreign_keys="ModulePrerequisite.prerequisite_module_id",
    )
