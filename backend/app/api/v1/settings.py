"""
app/api/v1/endpoints/settings.py

Endpoints for managing application settings, such as LLM provider selection.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from app.dependencies.auth import get_current_user
from app.db.session import get_db
from app.models.app_config import AppConfig
from app.models.user import User
from app.services.llm.provider_registry import PROVIDER_DEFINITIONS, get_provider_status

router = APIRouter()

class ProviderInfo(BaseModel):
    id: str
    name: str
    description: str
    capabilities: List[str]
    status: str

class LLMSettingsResponse(BaseModel):
    active_provider: str
    providers: List[ProviderInfo]

class LLMSettingsUpdate(BaseModel):
    provider_id: str

@router.get("/llm", response_model=LLMSettingsResponse)
async def get_llm_settings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get the current LLM settings and all available providers."""
    # Fetch active provider from DB
    result = await db.execute(select(AppConfig).where(AppConfig.key == "active_llm_provider"))
    config = result.scalar_one_or_none()
    
    active_provider = "gemini" # Default
    if config and isinstance(config.value, dict) and "provider_id" in config.value:
        active_provider = config.value["provider_id"]
        
    providers = []
    for pid, pdef in PROVIDER_DEFINITIONS.items():
        providers.append(
            ProviderInfo(
                id=pid,
                name=pdef["name"],
                description=pdef["description"],
                capabilities=pdef["capabilities"],
                status=get_provider_status(pid)
            )
        )
        
    return LLMSettingsResponse(
        active_provider=active_provider,
        providers=providers
    )

@router.put("/llm")
async def update_llm_settings(
    data: LLMSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update the active LLM provider."""
    pid = data.provider_id.lower()
    
    if pid not in PROVIDER_DEFINITIONS:
        raise HTTPException(status_code=400, detail=f"Unknown provider '{pid}'")
        
    status_str = get_provider_status(pid)
    if status_str != "Configured":
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot select {PROVIDER_DEFINITIONS[pid]['name']} because its status is '{status_str}'."
        )
        
    result = await db.execute(select(AppConfig).where(AppConfig.key == "active_llm_provider"))
    config = result.scalar_one_or_none()
    
    if config:
        config.value = {"provider_id": pid}
    else:
        config = AppConfig(key="active_llm_provider", value={"provider_id": pid})
        db.add(config)
        
    await db.commit()
    return {"status": "success", "active_provider": pid}
