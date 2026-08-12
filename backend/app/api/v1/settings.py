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
    api_key: str = None

@router.get("/llm", response_model=LLMSettingsResponse)
async def get_llm_settings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get the current LLM settings and all available providers."""
    # Fetch active provider from DB
    result = await db.execute(select(AppConfig).where(AppConfig.key == "active_llm_provider"))
    config = result.scalar_one_or_none()
    
    from app.core.config import settings
    active_provider = settings.PRIMARY_LLM # Default to .env configuration
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

import os
import re

@router.put("/llm")
async def update_llm_settings(
    data: LLMSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update the active LLM provider and optionally save API key."""
    pid = data.provider_id.lower()
    
    if pid not in PROVIDER_DEFINITIONS:
        raise HTTPException(status_code=400, detail=f"Unknown provider '{pid}'")
        
    pdef = PROVIDER_DEFINITIONS[pid]
    env_key = pdef["env_key"]
    
    # Save the key to .env if provided
    if data.api_key:
        env_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env")
        env_path = os.path.abspath(env_path)
        
        # Read existing .env
        env_content = ""
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                env_content = f.read()
                
        # Update or append the key
        pattern = re.compile(rf"^{env_key}=.*$", re.MULTILINE)
        if pattern.search(env_content):
            env_content = pattern.sub(f"{env_key}={data.api_key}", env_content)
        else:
            if env_content and not env_content.endswith('\n'):
                env_content += '\n'
            env_content += f"{env_key}={data.api_key}\n"
            
        with open(env_path, "w", encoding="utf-8") as f:
            f.write(env_content)
            
        # Update os.environ so the current process sees it immediately
        os.environ[env_key] = data.api_key
        
    status_str = get_provider_status(pid)
    if status_str != "Configured":
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot select {pdef['name']} because its status is '{status_str}'. Please provide an API key."
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
