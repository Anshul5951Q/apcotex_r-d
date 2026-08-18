"""
app/api/v1/recipe.py

Recipe Simulator API endpoints.
"""
import uuid
from fastapi import APIRouter, Depends, status

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.common import SuccessResponse
from app.schemas.recipe import (
    RecipeCycleCreate, RecipeCycleUpdate,
    RecipeCycleResponse, RecipeCycleDetailResponse,
    RecipeCandidateResponse,
    CustomerTrialCreate, CustomerTrialUpdate,
    CustomerTrialResponse,
    OptimizedRecipeCandidateResponse
)
from app.services.recipe_service import RecipeService

router = APIRouter(prefix="/recipe", tags=["Recipe Simulator"])


@router.post("/cycles", response_model=SuccessResponse[RecipeCycleResponse])
async def create_recipe_cycle(
    data: RecipeCycleCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    svc = RecipeService(db)
    cycle = await svc.create_cycle(data, current_user)
    return SuccessResponse(data=cycle)


@router.get("/cycles", response_model=SuccessResponse[list[RecipeCycleDetailResponse]])
async def list_recipe_cycles(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    svc = RecipeService(db)
    cycles = await svc.list_cycles_for_user(current_user.id)
    return SuccessResponse(data=cycles)


@router.get("/cycles/{cycle_id}", response_model=SuccessResponse[RecipeCycleDetailResponse])
async def get_recipe_cycle(
    cycle_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    svc = RecipeService(db)
    cycle = await svc.get_cycle(cycle_id)
    return SuccessResponse(data=cycle)


@router.patch("/cycles/{cycle_id}", response_model=SuccessResponse[RecipeCycleResponse])
async def update_recipe_cycle(
    cycle_id: uuid.UUID,
    data: RecipeCycleUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    svc = RecipeService(db)
    cycle = await svc.update_cycle(cycle_id, data)
    return SuccessResponse(data=cycle)


@router.post("/cycles/{cycle_id}/generate", response_model=SuccessResponse[list[RecipeCandidateResponse]])
async def generate_recipes(
    cycle_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    svc = RecipeService(db)
    candidates = await svc.generate_recipes(cycle_id)
    return SuccessResponse(data=candidates)


@router.get("/cycles/{cycle_id}/candidates", response_model=SuccessResponse[list[RecipeCandidateResponse]])
async def get_candidates(
    cycle_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    svc = RecipeService(db)
    cycle = await svc.get_cycle(cycle_id)
    return SuccessResponse(data=cycle.candidates)


@router.post("/cycles/{cycle_id}/select/{candidate_id}", response_model=SuccessResponse[RecipeCycleResponse])
async def select_candidate(
    cycle_id: uuid.UUID,
    candidate_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    svc = RecipeService(db)
    cycle = await svc.select_candidate(cycle_id, candidate_id)
    return SuccessResponse(data=cycle)


@router.post("/trials", response_model=SuccessResponse[CustomerTrialResponse])
async def create_trial(
    data: CustomerTrialCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    svc = RecipeService(db)
    trial = await svc.create_trial(data, current_user)
    return SuccessResponse(data=trial)


@router.patch("/trials/{trial_id}", response_model=SuccessResponse[CustomerTrialResponse])
async def update_trial(
    trial_id: uuid.UUID,
    data: CustomerTrialUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    svc = RecipeService(db)
    trial = await svc.update_trial(trial_id, data)
    return SuccessResponse(data=trial)


@router.post("/trials/{trial_id}/optimize", response_model=SuccessResponse[list[OptimizedRecipeCandidateResponse]])
async def generate_optimization(
    trial_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    svc = RecipeService(db)
    opts = await svc.generate_optimized_recipes(trial_id)
    return SuccessResponse(data=opts)


@router.get("/trials/{trial_id}/optimized", response_model=SuccessResponse[list[OptimizedRecipeCandidateResponse]])
async def get_optimized(
    trial_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    svc = RecipeService(db)
    opts = await svc.generate_optimized_recipes(trial_id) # if already generated returns them, else generates
    return SuccessResponse(data=opts)


@router.post("/trials/{trial_id}/select/{optimized_id}", response_model=SuccessResponse[CustomerTrialResponse])
async def select_optimized(
    trial_id: uuid.UUID,
    optimized_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    svc = RecipeService(db)
    trial = await svc.select_optimized(trial_id, optimized_id)
    return SuccessResponse(data=trial)
