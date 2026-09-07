from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class BusinessCategory(Base):
    __tablename__ = "business_categories"
    __table_args__ = {"schema": "reviewflow"}

    id: Mapped[UUID] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(50), unique=True)
    name: Mapped[str] = mapped_column(String(80))
    display_order: Mapped[int] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class ExperienceAttribute(Base):
    __tablename__ = "experience_attributes"
    __table_args__ = (UniqueConstraint("category_id", "slug"), {"schema": "reviewflow"})

    id: Mapped[UUID] = mapped_column(primary_key=True)
    category_id: Mapped[UUID] = mapped_column(ForeignKey("reviewflow.business_categories.id"))
    slug: Mapped[str] = mapped_column(String(50))
    label: Mapped[str] = mapped_column(String(80))
    display_order: Mapped[int] = mapped_column(Integer)
