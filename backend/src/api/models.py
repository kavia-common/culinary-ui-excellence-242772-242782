"""SQLAlchemy ORM models matching the MySQL schema in the database container."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all ORM models."""


class Recipe(Base):
    __tablename__ = "recipes"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    author_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)

    title: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cuisine: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)

    # Stored as enum in MySQL; we treat as string with check constraint.
    difficulty: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="easy"
    )

    prep_time_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    cook_time_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    servings: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    hero_image_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    is_published: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="1"
    )

    created_at: Mapped[Optional[str]] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
    updated_at: Mapped[Optional[str]] = mapped_column(
        DateTime,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

    steps: Mapped[list["RecipeStep"]] = relationship(
        "RecipeStep",
        back_populates="recipe",
        cascade="all, delete-orphan",
        order_by="RecipeStep.step_number",
    )

    ingredients: Mapped[list["RecipeIngredient"]] = relationship(
        "RecipeIngredient",
        back_populates="recipe",
        cascade="all, delete-orphan",
        order_by="RecipeIngredient.sort_order",
    )

    __table_args__ = (
        CheckConstraint(
            "difficulty in ('easy','medium','hard')",
            name="ck_recipes_difficulty",
        ),
    )


class Ingredient(Base):
    __tablename__ = "ingredients"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    canonical_name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)

    created_at: Mapped[Optional[str]] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )

    recipes: Mapped[list["RecipeIngredient"]] = relationship(
        "RecipeIngredient",
        back_populates="ingredient",
        cascade="all, delete-orphan",
    )


class RecipeIngredient(Base):
    __tablename__ = "recipe_ingredients"

    recipe_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("recipes.id", ondelete="CASCADE"),
        primary_key=True,
    )
    ingredient_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("ingredients.id", ondelete="RESTRICT"),
        primary_key=True,
    )

    quantity: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    unit: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    note: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )

    created_at: Mapped[Optional[str]] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )

    recipe: Mapped["Recipe"] = relationship("Recipe", back_populates="ingredients")
    ingredient: Mapped["Ingredient"] = relationship(
        "Ingredient", back_populates="recipes"
    )


class RecipeStep(Base):
    __tablename__ = "recipe_steps"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    recipe_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("recipes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    step_number: Mapped[int] = mapped_column(Integer, nullable=False)
    instruction: Mapped[str] = mapped_column(Text, nullable=False)

    media_image_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    created_at: Mapped[Optional[str]] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )

    recipe: Mapped["Recipe"] = relationship("Recipe", back_populates="steps")


class Reel(Base):
    __tablename__ = "reels"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    recipe_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("recipes.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    author_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    caption: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    video_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    poster_image_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)

    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    aspect_ratio: Mapped[str] = mapped_column(String(20), nullable=False, server_default="9:16")

    created_at: Mapped[Optional[str]] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
