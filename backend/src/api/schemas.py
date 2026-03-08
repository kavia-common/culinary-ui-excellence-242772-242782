"""Pydantic request/response schemas for the API."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, HttpUrl, conint, confloat


Difficulty = Literal["easy", "medium", "hard"]


class APIError(BaseModel):
    """Standard error payload returned by the API."""

    code: str = Field(..., description="Stable error code identifier (snake_case).")
    message: str = Field(..., description="Human-readable error message.")
    details: Optional[dict] = Field(default=None, description="Optional extra error details.")


class IngredientBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=120, description="Display name for the ingredient.")
    canonical_name: str = Field(
        ...,
        min_length=1,
        max_length=120,
        description="Canonical name (unique) used for deduplication/search.",
        pattern=r"^[a-z0-9][a-z0-9 \-']*$",
    )


class IngredientCreate(IngredientBase):
    pass


class IngredientUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    canonical_name: Optional[str] = Field(default=None, min_length=1, max_length=120, pattern=r"^[a-z0-9][a-z0-9 \-']*$")


class IngredientOut(IngredientBase):
    id: int = Field(..., description="Ingredient ID.")
    created_at: Optional[datetime] = Field(default=None, description="Creation timestamp.")

    class Config:
        from_attributes = True


class RecipeBase(BaseModel):
    author_user_id: int = Field(..., ge=1, description="Author user ID.")
    title: str = Field(..., min_length=1, max_length=200, description="Recipe title.")
    description: Optional[str] = Field(default=None, description="Recipe description.")
    cuisine: Optional[str] = Field(default=None, max_length=80, description="Cuisine label.")
    difficulty: Difficulty = Field(default="easy", description="Difficulty level.")
    prep_time_minutes: Optional[conint(ge=0)] = Field(default=None, description="Prep time in minutes.")
    cook_time_minutes: Optional[conint(ge=0)] = Field(default=None, description="Cook time in minutes.")
    servings: Optional[conint(ge=1)] = Field(default=None, description="Servings count.")
    hero_image_url: Optional[HttpUrl] = Field(default=None, description="Hero image URL.")
    is_published: bool = Field(default=True, description="Published flag.")


class RecipeCreate(RecipeBase):
    pass


class RecipeUpdate(BaseModel):
    author_user_id: Optional[int] = Field(default=None, ge=1)
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None
    cuisine: Optional[str] = Field(default=None, max_length=80)
    difficulty: Optional[Difficulty] = None
    prep_time_minutes: Optional[conint(ge=0)] = None
    cook_time_minutes: Optional[conint(ge=0)] = None
    servings: Optional[conint(ge=1)] = None
    hero_image_url: Optional[HttpUrl] = None
    is_published: Optional[bool] = None


class RecipeOut(RecipeBase):
    id: int = Field(..., description="Recipe ID.")
    created_at: Optional[datetime] = Field(default=None)
    updated_at: Optional[datetime] = Field(default=None)

    class Config:
        from_attributes = True


class RecipeIngredientBase(BaseModel):
    ingredient_id: int = Field(..., ge=1, description="Ingredient ID.")
    quantity: Optional[confloat(ge=0)] = Field(default=None, description="Quantity (decimal).")
    unit: Optional[str] = Field(default=None, max_length=32, description="Unit (e.g., g, tbsp).")
    note: Optional[str] = Field(default=None, max_length=255, description="Optional note (e.g., 'finely chopped').")
    sort_order: conint(ge=0) = Field(default=0, description="Ordering among ingredients.")


class RecipeIngredientCreate(RecipeIngredientBase):
    pass


class RecipeIngredientUpdate(BaseModel):
    quantity: Optional[confloat(ge=0)] = None
    unit: Optional[str] = Field(default=None, max_length=32)
    note: Optional[str] = Field(default=None, max_length=255)
    sort_order: Optional[conint(ge=0)] = None


class RecipeIngredientOut(RecipeIngredientBase):
    recipe_id: int = Field(..., description="Recipe ID.")
    ingredient: Optional[IngredientOut] = Field(default=None, description="Ingredient details (if expanded).")

    class Config:
        from_attributes = True


class RecipeStepBase(BaseModel):
    step_number: conint(ge=1) = Field(..., description="Step number starting at 1.")
    instruction: str = Field(..., min_length=1, description="Step instruction.")
    media_image_url: Optional[HttpUrl] = Field(default=None, description="Optional image URL for the step.")
    duration_seconds: Optional[conint(ge=0)] = Field(default=None, description="Optional duration in seconds.")


class RecipeStepCreate(RecipeStepBase):
    pass


class RecipeStepUpdate(BaseModel):
    step_number: Optional[conint(ge=1)] = None
    instruction: Optional[str] = Field(default=None, min_length=1)
    media_image_url: Optional[HttpUrl] = None
    duration_seconds: Optional[conint(ge=0)] = None


class RecipeStepOut(RecipeStepBase):
    id: int = Field(..., description="Step ID.")
    recipe_id: int = Field(..., description="Parent recipe ID.")
    created_at: Optional[datetime] = Field(default=None)

    class Config:
        from_attributes = True


class ReelBase(BaseModel):
    recipe_id: Optional[int] = Field(default=None, ge=1, description="Optional associated recipe ID.")
    author_user_id: int = Field(..., ge=1, description="Author user ID.")
    title: str = Field(..., min_length=1, max_length=200, description="Reel title.")
    caption: Optional[str] = Field(default=None, description="Caption text.")
    video_url: HttpUrl = Field(..., description="Video URL.")
    poster_image_url: Optional[HttpUrl] = Field(default=None, description="Poster/thumbnail URL.")
    duration_seconds: Optional[conint(ge=0)] = Field(default=None, description="Duration in seconds.")
    aspect_ratio: str = Field(default="9:16", max_length=20, description="Aspect ratio string.")


class ReelCreate(ReelBase):
    pass


class ReelOut(ReelBase):
    id: int = Field(..., description="Reel ID.")
    created_at: Optional[datetime] = Field(default=None)

    class Config:
        from_attributes = True


class VersionOut(BaseModel):
    version: str = Field(..., description="Backend version string.")
    service: str = Field(..., description="Service name.")
    environment: Optional[str] = Field(default=None, description="Deployment environment label (optional).")
    db_connected: bool = Field(..., description="Whether the service can connect to the DB right now.")
