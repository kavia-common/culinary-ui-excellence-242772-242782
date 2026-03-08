from __future__ import annotations

import os
from typing import Annotated, Optional

from fastapi import Depends, FastAPI, Query, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from src.api.db import get_db, get_engine
from src.api.errors import http_error
from src.api.models import Ingredient, Reel, Recipe, RecipeIngredient, RecipeStep
from src.api.schemas import (
    IngredientCreate,
    IngredientOut,
    IngredientUpdate,
    RecipeCreate,
    RecipeIngredientCreate,
    RecipeIngredientOut,
    RecipeIngredientUpdate,
    RecipeOut,
    RecipeStepCreate,
    RecipeStepOut,
    RecipeStepUpdate,
    RecipeUpdate,
    ReelCreate,
    ReelOut,
    VersionOut,
)

openapi_tags = [
    {"name": "Meta", "description": "Service health, version, and diagnostics endpoints."},
    {"name": "Recipes", "description": "CRUD endpoints for recipes and their nested data."},
    {"name": "Ingredients", "description": "CRUD endpoints for ingredients."},
    {"name": "Recipe Steps", "description": "CRUD endpoints for recipe steps."},
    {"name": "Recipe Ingredients", "description": "CRUD endpoints for recipe ingredient lines."},
    {"name": "Reels", "description": "Reels feed and reel CRUD."},
]

app = FastAPI(
    title="Culinary UI Excellence Backend",
    description=(
        "FastAPI backend providing recipe/ingredient/step CRUD and a reels feed. "
        "Backed by a MySQL database."
    ),
    version=os.getenv("APP_VERSION", "0.1.0"),
    openapi_tags=openapi_tags,
)

# CORS: compatible with local dev + deployed preview environments.
# If FRONTEND_ORIGINS is not provided, we fall back to '*' to avoid blocking the UI in template environments.
frontend_origins = os.getenv("FRONTEND_ORIGINS", "*")
allow_origins = (
    ["*"]
    if frontend_origins.strip() == "*"
    else [o.strip() for o in frontend_origins.split(",") if o.strip()]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DbDep = Annotated[Session, Depends(get_db)]


def _integrity_error_to_http(exc: IntegrityError):
    """Map DB constraint violations to a consistent 409 response."""
    return http_error(
        code="integrity_error",
        message="Database integrity constraint failed.",
        status_code=status.HTTP_409_CONFLICT,
        details={"error": str(exc.orig) if getattr(exc, "orig", None) else str(exc)},
    )


# --- Meta endpoints ---------------------------------------------------------


@app.get(
    "/",
    tags=["Meta"],
    summary="Health check",
    description="Basic liveness probe endpoint.",
)
# PUBLIC_INTERFACE
def health_check():
    """Return a simple health check response."""
    return {"message": "Healthy"}


@app.get(
    "/health",
    tags=["Meta"],
    summary="Health check (DB aware)",
    description="Health endpoint that also checks DB connectivity.",
    response_model=dict,
)
# PUBLIC_INTERFACE
def health_check_db(db: DbDep):
    """Return health information and DB connectivity status."""
    try:
        db.execute(select(1))
        return {"status": "ok", "db_connected": True}
    except Exception:
        return {"status": "degraded", "db_connected": False}


@app.get(
    "/version",
    tags=["Meta"],
    summary="Service version",
    description="Returns version metadata and a quick DB connectivity indicator.",
    response_model=VersionOut,
)
# PUBLIC_INTERFACE
def version(db: DbDep):
    """Return backend version metadata."""
    db_connected = True
    try:
        db.execute(select(1))
    except Exception:
        db_connected = False

    return VersionOut(
        version=app.version,
        service="backend",
        environment=os.getenv("APP_ENV"),
        db_connected=db_connected,
    )


# --- Ingredients ------------------------------------------------------------


@app.post(
    "/ingredients",
    tags=["Ingredients"],
    summary="Create ingredient",
    response_model=IngredientOut,
    status_code=status.HTTP_201_CREATED,
)
# PUBLIC_INTERFACE
def create_ingredient(payload: IngredientCreate, db: DbDep):
    """Create a new ingredient."""
    ing = Ingredient(name=payload.name, canonical_name=payload.canonical_name)
    db.add(ing)
    try:
        db.flush()
    except IntegrityError as exc:
        raise _integrity_error_to_http(exc) from exc
    return ing


@app.get(
    "/ingredients",
    tags=["Ingredients"],
    summary="List ingredients",
    response_model=list[IngredientOut],
)
# PUBLIC_INTERFACE
def list_ingredients(
    db: DbDep,
    q: Optional[str] = Query(default=None, description="Search by name/canonical_name."),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    """List ingredients with optional query search."""
    stmt = select(Ingredient)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(Ingredient.name.like(like), Ingredient.canonical_name.like(like))
        )
    stmt = stmt.order_by(Ingredient.name.asc()).limit(limit).offset(offset)
    return list(db.scalars(stmt).all())


@app.get(
    "/ingredients/{ingredient_id}",
    tags=["Ingredients"],
    summary="Get ingredient",
    response_model=IngredientOut,
)
# PUBLIC_INTERFACE
def get_ingredient(ingredient_id: int, db: DbDep):
    """Get an ingredient by ID."""
    ing = db.get(Ingredient, ingredient_id)
    if not ing:
        raise http_error(code="not_found", message="Ingredient not found.", status_code=404)
    return ing


@app.patch(
    "/ingredients/{ingredient_id}",
    tags=["Ingredients"],
    summary="Update ingredient",
    response_model=IngredientOut,
)
# PUBLIC_INTERFACE
def update_ingredient(ingredient_id: int, payload: IngredientUpdate, db: DbDep):
    """Update an ingredient (partial update)."""
    ing = db.get(Ingredient, ingredient_id)
    if not ing:
        raise http_error(code="not_found", message="Ingredient not found.", status_code=404)

    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(ing, k, v)

    try:
        db.flush()
    except IntegrityError as exc:
        raise _integrity_error_to_http(exc) from exc

    return ing


@app.delete(
    "/ingredients/{ingredient_id}",
    tags=["Ingredients"],
    summary="Delete ingredient",
    status_code=status.HTTP_204_NO_CONTENT,
)
# PUBLIC_INTERFACE
def delete_ingredient(ingredient_id: int, db: DbDep):
    """Delete ingredient by ID."""
    ing = db.get(Ingredient, ingredient_id)
    if not ing:
        raise http_error(code="not_found", message="Ingredient not found.", status_code=404)

    db.delete(ing)
    return None


# --- Recipes ----------------------------------------------------------------


@app.post(
    "/recipes",
    tags=["Recipes"],
    summary="Create recipe",
    response_model=RecipeOut,
    status_code=status.HTTP_201_CREATED,
)
# PUBLIC_INTERFACE
def create_recipe(payload: RecipeCreate, db: DbDep):
    """Create a recipe."""
    recipe = Recipe(**payload.model_dump())
    db.add(recipe)
    try:
        db.flush()
    except IntegrityError as exc:
        raise _integrity_error_to_http(exc) from exc
    return recipe


@app.get(
    "/recipes",
    tags=["Recipes"],
    summary="List recipes",
    response_model=list[RecipeOut],
)
# PUBLIC_INTERFACE
def list_recipes(
    db: DbDep,
    q: Optional[str] = Query(default=None, description="Search by title/description."),
    cuisine: Optional[str] = Query(default=None, description="Filter by cuisine."),
    difficulty: Optional[str] = Query(
        default=None, description="Filter by difficulty (easy|medium|hard)."
    ),
    is_published: Optional[bool] = Query(default=True, description="Filter by published flag."),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    """List recipes with filters and pagination."""
    stmt = select(Recipe)
    filters = []

    if q:
        like = f"%{q.strip()}%"
        filters.append(or_(Recipe.title.like(like), Recipe.description.like(like)))
    if cuisine:
        filters.append(Recipe.cuisine == cuisine)
    if difficulty:
        filters.append(Recipe.difficulty == difficulty)
    if is_published is not None:
        filters.append(Recipe.is_published == is_published)

    if filters:
        stmt = stmt.where(and_(*filters))

    stmt = stmt.order_by(Recipe.created_at.desc()).limit(limit).offset(offset)
    return list(db.scalars(stmt).all())


@app.get(
    "/recipes/{recipe_id}",
    tags=["Recipes"],
    summary="Get recipe",
    description="Fetch a recipe by ID. Use include_steps/include_ingredients to eager-load nested data.",
    response_model=RecipeOut,
)
# PUBLIC_INTERFACE
def get_recipe(
    recipe_id: int,
    db: DbDep,
    include_steps: bool = Query(
        default=False,
        description="If true, eager-load steps (steps are also available via /recipes/{id}/steps).",
    ),
    include_ingredients: bool = Query(
        default=False,
        description="If true, eager-load ingredient lines (also via /recipes/{id}/ingredients).",
    ),
):
    """Get a recipe by ID."""
    stmt = select(Recipe).where(Recipe.id == recipe_id)
    if include_steps:
        stmt = stmt.options(joinedload(Recipe.steps))
    if include_ingredients:
        stmt = stmt.options(
            joinedload(Recipe.ingredients).joinedload(RecipeIngredient.ingredient)
        )

    recipe = db.scalars(stmt).first()
    if not recipe:
        raise http_error(code="not_found", message="Recipe not found.", status_code=404)
    return recipe


@app.patch(
    "/recipes/{recipe_id}",
    tags=["Recipes"],
    summary="Update recipe",
    response_model=RecipeOut,
)
# PUBLIC_INTERFACE
def update_recipe(recipe_id: int, payload: RecipeUpdate, db: DbDep):
    """Update a recipe (partial update)."""
    recipe = db.get(Recipe, recipe_id)
    if not recipe:
        raise http_error(code="not_found", message="Recipe not found.", status_code=404)

    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(recipe, k, v)

    try:
        db.flush()
    except IntegrityError as exc:
        raise _integrity_error_to_http(exc) from exc

    return recipe


@app.delete(
    "/recipes/{recipe_id}",
    tags=["Recipes"],
    summary="Delete recipe",
    status_code=status.HTTP_204_NO_CONTENT,
)
# PUBLIC_INTERFACE
def delete_recipe(recipe_id: int, db: DbDep):
    """Delete recipe by ID (cascades steps and ingredient lines)."""
    recipe = db.get(Recipe, recipe_id)
    if not recipe:
        raise http_error(code="not_found", message="Recipe not found.", status_code=404)
    db.delete(recipe)
    return None


# --- Recipe Steps -----------------------------------------------------------


@app.get(
    "/recipes/{recipe_id}/steps",
    tags=["Recipe Steps"],
    summary="List recipe steps",
    response_model=list[RecipeStepOut],
)
# PUBLIC_INTERFACE
def list_recipe_steps(recipe_id: int, db: DbDep):
    """List steps for a recipe ordered by step_number."""
    if not db.get(Recipe, recipe_id):
        raise http_error(code="not_found", message="Recipe not found.", status_code=404)

    stmt = (
        select(RecipeStep)
        .where(RecipeStep.recipe_id == recipe_id)
        .order_by(RecipeStep.step_number.asc())
    )
    return list(db.scalars(stmt).all())


@app.post(
    "/recipes/{recipe_id}/steps",
    tags=["Recipe Steps"],
    summary="Create recipe step",
    response_model=RecipeStepOut,
    status_code=status.HTTP_201_CREATED,
)
# PUBLIC_INTERFACE
def create_recipe_step(recipe_id: int, payload: RecipeStepCreate, db: DbDep):
    """Create a step for a recipe."""
    if not db.get(Recipe, recipe_id):
        raise http_error(code="not_found", message="Recipe not found.", status_code=404)

    step = RecipeStep(recipe_id=recipe_id, **payload.model_dump())
    db.add(step)
    db.flush()
    return step


@app.patch(
    "/recipes/{recipe_id}/steps/{step_id}",
    tags=["Recipe Steps"],
    summary="Update recipe step",
    response_model=RecipeStepOut,
)
# PUBLIC_INTERFACE
def update_recipe_step(recipe_id: int, step_id: int, payload: RecipeStepUpdate, db: DbDep):
    """Update a recipe step by ID."""
    step = db.get(RecipeStep, step_id)
    if not step or step.recipe_id != recipe_id:
        raise http_error(code="not_found", message="Step not found.", status_code=404)

    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(step, k, v)

    db.flush()
    return step


@app.delete(
    "/recipes/{recipe_id}/steps/{step_id}",
    tags=["Recipe Steps"],
    summary="Delete recipe step",
    status_code=status.HTTP_204_NO_CONTENT,
)
# PUBLIC_INTERFACE
def delete_recipe_step(recipe_id: int, step_id: int, db: DbDep):
    """Delete a recipe step."""
    step = db.get(RecipeStep, step_id)
    if not step or step.recipe_id != recipe_id:
        raise http_error(code="not_found", message="Step not found.", status_code=404)
    db.delete(step)
    return None


# --- Recipe Ingredients -----------------------------------------------------


@app.get(
    "/recipes/{recipe_id}/ingredients",
    tags=["Recipe Ingredients"],
    summary="List recipe ingredient lines",
    response_model=list[RecipeIngredientOut],
)
# PUBLIC_INTERFACE
def list_recipe_ingredients(
    recipe_id: int,
    db: DbDep,
    expand: bool = Query(
        default=True,
        description="If true, includes full ingredient object for each line.",
    ),
):
    """List ingredient lines for a recipe."""
    if not db.get(Recipe, recipe_id):
        raise http_error(code="not_found", message="Recipe not found.", status_code=404)

    stmt = (
        select(RecipeIngredient)
        .where(RecipeIngredient.recipe_id == recipe_id)
        .order_by(RecipeIngredient.sort_order.asc())
    )
    if expand:
        stmt = stmt.options(joinedload(RecipeIngredient.ingredient))

    return list(db.scalars(stmt).all())


@app.post(
    "/recipes/{recipe_id}/ingredients",
    tags=["Recipe Ingredients"],
    summary="Add ingredient line to recipe",
    response_model=RecipeIngredientOut,
    status_code=status.HTTP_201_CREATED,
)
# PUBLIC_INTERFACE
def create_recipe_ingredient(recipe_id: int, payload: RecipeIngredientCreate, db: DbDep):
    """Add an ingredient line to a recipe."""
    if not db.get(Recipe, recipe_id):
        raise http_error(code="not_found", message="Recipe not found.", status_code=404)

    ingredient = db.get(Ingredient, payload.ingredient_id)
    if not ingredient:
        raise http_error(code="not_found", message="Ingredient not found.", status_code=404)

    line = RecipeIngredient(recipe_id=recipe_id, **payload.model_dump())
    db.add(line)
    try:
        db.flush()
    except IntegrityError as exc:
        raise _integrity_error_to_http(exc) from exc

    line.ingredient = ingredient
    return line


@app.patch(
    "/recipes/{recipe_id}/ingredients/{ingredient_id}",
    tags=["Recipe Ingredients"],
    summary="Update ingredient line",
    response_model=RecipeIngredientOut,
)
# PUBLIC_INTERFACE
def update_recipe_ingredient(
    recipe_id: int,
    ingredient_id: int,
    payload: RecipeIngredientUpdate,
    db: DbDep,
):
    """Update a recipe ingredient line (recipe_id + ingredient_id composite PK)."""
    stmt = (
        select(RecipeIngredient)
        .where(
            and_(
                RecipeIngredient.recipe_id == recipe_id,
                RecipeIngredient.ingredient_id == ingredient_id,
            )
        )
        .options(joinedload(RecipeIngredient.ingredient))
    )
    line = db.scalars(stmt).first()
    if not line:
        raise http_error(
            code="not_found",
            message="Recipe ingredient line not found.",
            status_code=404,
        )

    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(line, k, v)

    db.flush()
    return line


@app.delete(
    "/recipes/{recipe_id}/ingredients/{ingredient_id}",
    tags=["Recipe Ingredients"],
    summary="Remove ingredient line",
    status_code=status.HTTP_204_NO_CONTENT,
)
# PUBLIC_INTERFACE
def delete_recipe_ingredient(recipe_id: int, ingredient_id: int, db: DbDep):
    """Remove an ingredient line from a recipe."""
    stmt = select(RecipeIngredient).where(
        and_(
            RecipeIngredient.recipe_id == recipe_id,
            RecipeIngredient.ingredient_id == ingredient_id,
        )
    )
    line = db.scalars(stmt).first()
    if not line:
        raise http_error(
            code="not_found",
            message="Recipe ingredient line not found.",
            status_code=404,
        )
    db.delete(line)
    return None


# --- Reels ------------------------------------------------------------------


@app.get(
    "/reels",
    tags=["Reels"],
    summary="Reels feed",
    description="List reels ordered by created_at descending.",
    response_model=list[ReelOut],
)
# PUBLIC_INTERFACE
def list_reels(
    db: DbDep,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    """Return reels feed. Can be empty if no reels exist in DB."""
    stmt = select(Reel).order_by(Reel.created_at.desc()).limit(limit).offset(offset)
    return list(db.scalars(stmt).all())


@app.post(
    "/reels",
    tags=["Reels"],
    summary="Create reel",
    response_model=ReelOut,
    status_code=status.HTTP_201_CREATED,
)
# PUBLIC_INTERFACE
def create_reel(payload: ReelCreate, db: DbDep):
    """Create a reel."""
    if payload.recipe_id is not None and not db.get(Recipe, payload.recipe_id):
        raise http_error(code="not_found", message="Recipe not found.", status_code=404)

    reel = Reel(**payload.model_dump())
    db.add(reel)
    try:
        db.flush()
    except IntegrityError as exc:
        raise _integrity_error_to_http(exc) from exc
    return reel


@app.get(
    "/reels/{reel_id}",
    tags=["Reels"],
    summary="Get reel",
    response_model=ReelOut,
)
# PUBLIC_INTERFACE
def get_reel(reel_id: int, db: DbDep):
    """Get reel by ID."""
    reel = db.get(Reel, reel_id)
    if not reel:
        raise http_error(code="not_found", message="Reel not found.", status_code=404)
    return reel


@app.delete(
    "/reels/{reel_id}",
    tags=["Reels"],
    summary="Delete reel",
    status_code=status.HTTP_204_NO_CONTENT,
)
# PUBLIC_INTERFACE
def delete_reel(reel_id: int, db: DbDep):
    """Delete reel by ID."""
    reel = db.get(Reel, reel_id)
    if not reel:
        raise http_error(code="not_found", message="Reel not found.", status_code=404)
    db.delete(reel)
    return None


@app.on_event("startup")
def _startup_check_db():
    """
    On startup, attempt to initialize the engine.

    This does not create tables (schema already exists) — it only ensures the URL can be built.
    """
    get_engine()
