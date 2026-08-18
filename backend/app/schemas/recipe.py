"""
app/schemas/recipe.py

Pydantic schemas for the Recipe Simulator workflow, including LLM structured output schemas.
"""
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator
import uuid


# ────────────────────────────────────────────────────────────────────────────
# Core Request & Response Schemas
# ────────────────────────────────────────────────────────────────────────────

class RecipePropertyDef(BaseModel):
    id: str
    feature: str
    unit: str
    min: Optional[str] = None
    max: Optional[str] = None
    category: Optional[str] = None
    dataType: Optional[str] = None


class CompetitorData(BaseModel):
    name: str
    values: dict[str, str]


class RecipeCycleCreate(BaseModel):
    research_run_id: uuid.UUID
    target_properties: list[RecipePropertyDef] = Field(default_factory=list)
    competitor_data: list[CompetitorData] = Field(default_factory=list)


class RecipeCycleUpdate(BaseModel):
    target_properties: Optional[list[RecipePropertyDef]] = None
    competitor_data: Optional[list[CompetitorData]] = None


class RecipeCandidateResponse(BaseModel):
    id: uuid.UUID
    cycle_id: uuid.UUID
    rank: int
    name: str
    recipe_data: dict[str, Any]
    patent_references: list[str]
    evidence_coverage_score: int
    is_selected: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class RecipeCycleResponse(BaseModel):
    id: uuid.UUID
    research_run_id: Optional[uuid.UUID] = None
    report_metadata_id: Optional[uuid.UUID] = None
    compound_name: str
    status: str
    target_properties: list[dict[str, Any]]
    competitor_data: list[dict[str, Any]]
    selected_candidate_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class RecipeCycleDetailResponse(RecipeCycleResponse):
    candidates: list[RecipeCandidateResponse] = Field(default_factory=list)
    # Trials are added manually in the service layer if needed
    model_config = ConfigDict(from_attributes=True)


class CustomerTrialCreate(BaseModel):
    selected_candidate_id: uuid.UUID
    feedback_text: Optional[str] = None
    actual_values: dict[str, str] = Field(default_factory=dict)
    target_values: dict[str, str] = Field(default_factory=dict)


class CustomerTrialUpdate(BaseModel):
    feedback_text: Optional[str] = None
    actual_values: Optional[dict[str, str]] = None
    target_values: Optional[dict[str, str]] = None


class OptimizedRecipeCandidateResponse(BaseModel):
    id: uuid.UUID
    trial_id: uuid.UUID
    revision_label: str
    name: str
    recipe_data: dict[str, Any]
    changed_parameters: list[dict[str, Any]]
    predicted_impacts: list[dict[str, Any]]
    is_selected: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class CustomerTrialResponse(BaseModel):
    id: uuid.UUID
    cycle_id: uuid.UUID
    selected_candidate_id: uuid.UUID
    status: str
    feedback_text: Optional[str] = None
    actual_values: dict[str, str]
    target_values: dict[str, str]
    selected_optimized_id: Optional[uuid.UUID] = None
    optimized_candidates: list[OptimizedRecipeCandidateResponse] = Field(default_factory=list)
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ────────────────────────────────────────────────────────────────────────────
# LLM Structured Output Schemas (Sent to gemini for generation)
# ────────────────────────────────────────────────────────────────────────────

class LLMRecipeParameter(BaseModel):
    name: str = Field(description="Parameter name (e.g. BD/ACN Ratio, Water, Initiator)")
    value: str = Field(description="Parameter value (e.g. 74/26, 185, 0.45)")
    unit: str = Field(description="Unit (e.g. phr, %)")
    source: str = Field(description="Must be exactly 'patent' or 'inferred'")
    patent_ref: Optional[str] = Field(description="If source=patent, the specific patent number supporting this value. E.g. US20250075019A1", default=None)


class LLMRecipeCandidate(BaseModel):
    name: str = Field(description="Short name for the recipe (e.g. 'Recipe 1')")
    bd_acn_ratio: str = Field(description="Butadiene to Acrylonitrile ratio")
    polymerization_method: str = Field(description="e.g. Cold Emulsion, Warm Emulsion")
    temperature: str = Field(description="Reaction temperature")
    water: str = Field(description="Water amount in phr")
    emulsifier: str = Field(description="Emulsifier details")
    initiator: str = Field(description="Initiator details")
    chain_transfer_agent: str = Field(description="Chain transfer agent details")
    coagulant: str = Field(description="Coagulant details")
    conversion: str = Field(description="Target conversion %")
    reaction_time: str = Field(description="Reaction duration")
    expected_bound_acn: str = Field(description="Expected Bound ACN %")
    expected_mooney: str = Field(description="Expected Mooney viscosity")
    
    # Detailed parameter list for the UI
    parameters: list[LLMRecipeParameter] = Field(description="Complete list of all formulation and process parameters. Every parameter should explicitly mention if it is patent-supported or inferred.")
    
    patent_references: list[str] = Field(description="List of all patents used to build this recipe.")
    rationale: str = Field(description="Explanation of why these parameters were chosen to meet the target constraints.")
    notes: str = Field(description="Any extra synthesis notes, sequence of addition, etc.")


class LLMRecipeSet(BaseModel):
    recipes: list[LLMRecipeCandidate] = Field(description="Exactly 5 distinct recipe formulations", min_length=5, max_length=5)


class LLMOptimizedChange(BaseModel):
    parameter: str = Field(description="Name of the changed parameter (e.g. Chain Transfer Agent)")
    previous: str = Field(description="Previous value in the original recipe")
    revised: str = Field(description="New value in this optimized revision")
    rationale: str = Field(description="Chemical/Process reason for this change")


class LLMOptimizedImpact(BaseModel):
    property: str = Field(description="Name of the property expected to change (e.g. Mooney, Hardness)")
    previous_value: str = Field(description="Previous expected value (or actual value from trial)")
    predicted_value: str = Field(description="New predicted value after the change")


class LLMOptimizedRecipeCandidate(BaseModel):
    revision_label: str = Field(description="Single letter revision label: 'A', 'B', or 'C'")
    name: str = Field(description="Full name, e.g. 'Recipe 2 – Revision A'")
    
    # The new full recipe state (same as original, but with changed values applied)
    bd_acn_ratio: str
    polymerization_method: str
    temperature: str
    water: str
    emulsifier: str
    initiator: str
    chain_transfer_agent: str
    coagulant: str
    conversion: str
    reaction_time: str
    
    parameters: list[LLMRecipeParameter] = Field(description="Complete list of all parameters for this new revision")
    
    changed_parameters: list[LLMOptimizedChange] = Field(description="Explicit list of what changed vs the selected recipe")
    predicted_impacts: list[LLMOptimizedImpact] = Field(description="Explicit list of properties expected to change as a result")
    rationale: str = Field(description="Overall explanation of how this revision addresses the customer feedback")


class LLMOptimizationSet(BaseModel):
    optimized_recipes: list[LLMOptimizedRecipeCandidate] = Field(description="Exactly 3 distinct optimized recipe revisions", min_length=3, max_length=3)
