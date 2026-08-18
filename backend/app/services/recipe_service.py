"""
app/services/recipe_service.py

Business logic for the Recipe Simulator workflow.
Handles RecipeCycle, RecipeCandidate, CustomerTrial, and OptimizedRecipeCandidate creation and LLM interactions.
"""
import logging
import json
import uuid
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from fastapi import HTTPException, status

from app.models.recipe_cycle import RecipeCycle, RecipeCycleStatus
from app.models.recipe_candidate import RecipeCandidate
from app.models.customer_trial import CustomerTrial, TrialStatus
from app.models.optimized_recipe_candidate import OptimizedRecipeCandidate
from app.models.research_run import ResearchRun
from app.models.patent_extraction import PatentExtraction
from app.models.extracted_parameter import ExtractedParameter
from app.models.report_metadata import ReportMetadata
from app.models.user import User

from app.schemas.recipe import (
    RecipeCycleCreate, RecipeCycleUpdate,
    CustomerTrialCreate, CustomerTrialUpdate,
    LLMRecipeSet, LLMOptimizationSet
)

from app.services.llm.llm_client import DynamicLLMClient
from app.services.prompts.patent_prompts import (
    RECIPE_GENERATION_SYSTEM_PROMPT,
    RECIPE_OPTIMIZATION_SYSTEM_PROMPT
)
from app.services.usage_logger import UsageLogger
from app.core.telemetry import set_current_stage, TelemetryStage, set_current_operation

logger = logging.getLogger(__name__)

class RecipeService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.llm_client = DynamicLLMClient()

    async def _build_patent_context_summary(self, research_run_id: uuid.UUID) -> dict:
        """
        Builds a compact summary of extracted patent parameters to send to the LLM.
        This ensures we stay within the 15,000 token limit.
        """
        result = await self.session.execute(
            select(PatentExtraction)
            .where(PatentExtraction.research_run_id == research_run_id)
            .options(selectinload(PatentExtraction.parameters))
        )
        extractions = result.scalars().all()
        
        context = []
        for ext in extractions:
            # We want to compact the parameters, picking only relevant synthesis params
            params = []
            for p in ext.parameters:
                # Discard low-value params to save tokens
                if p.category in ["Synthesis Parameters", "Polymerization Conditions", "Monomer Ratios", "Monomer Details", "Target Properties"]:
                    params.append({
                        "name": p.name,
                        "value": p.value,
                        "unit": p.unit
                    })
            if params:
                context.append({
                    "patent": ext.patent_number,
                    "title": ext.title,
                    "synthesis_parameters": params
                })
                
        return {"extracted_patents": context}

    # ── Recipe Cycle Management ────────────────────────────────────────────────

    async def create_cycle(self, data: RecipeCycleCreate, current_user: User) -> RecipeCycle:
        run = await self.session.get(ResearchRun, data.research_run_id)
        if not run:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Research run not found")

        # Find latest report
        report_result = await self.session.execute(
            select(ReportMetadata).where(ReportMetadata.research_run_id == data.research_run_id).order_by(ReportMetadata.version.desc()).limit(1)
        )
        report = report_result.scalar_one_or_none()

        patent_context = await self._build_patent_context_summary(data.research_run_id)

        cycle = RecipeCycle(
            research_run_id=data.research_run_id,
            report_metadata_id=report.id if report else None,
            created_by=current_user.id,
            compound_name=run.compound_name,
            status=RecipeCycleStatus.STEP1,
            target_properties=[p.model_dump(exclude_none=True) for p in data.target_properties],
            competitor_data=[c.model_dump() for c in data.competitor_data],
            patent_context_summary=patent_context
        )
        self.session.add(cycle)
        await self.session.commit()
        await self.session.refresh(cycle)
        return cycle

    async def get_cycle(self, cycle_id: uuid.UUID) -> RecipeCycle:
        result = await self.session.execute(
            select(RecipeCycle)
            .where(RecipeCycle.id == cycle_id)
            .options(
                selectinload(RecipeCycle.candidates),
                selectinload(RecipeCycle.trials).selectinload(CustomerTrial.optimized_candidates)
            )
        )
        cycle = result.scalar_one_or_none()
        if not cycle:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Recipe cycle not found")
        return cycle

    async def update_cycle(self, cycle_id: uuid.UUID, data: RecipeCycleUpdate) -> RecipeCycle:
        cycle = await self.get_cycle(cycle_id)
        if data.target_properties is not None:
            cycle.target_properties = [p.model_dump(exclude_none=True) for p in data.target_properties]
        if data.competitor_data is not None:
            cycle.competitor_data = [c.model_dump() for c in data.competitor_data]
        await self.session.commit()
        await self.session.refresh(cycle)
        return cycle

    async def list_cycles_for_user(self, user_id: uuid.UUID) -> list[RecipeCycle]:
        result = await self.session.execute(
            select(RecipeCycle)
            .where(RecipeCycle.created_by == user_id)
            .order_by(RecipeCycle.created_at.desc())
            .options(
                selectinload(RecipeCycle.candidates),
                selectinload(RecipeCycle.trials).selectinload(CustomerTrial.optimized_candidates)
            )
        )
        return list(result.scalars().all())

    # ── Recipe Generation ───────────────────────────────────────────────────────

    def _calculate_evidence_coverage(self, recipe: dict) -> int:
        """Calculate score based on how many params are patent-derived."""
        params = recipe.get("parameters", [])
        if not params:
            return 0
        patent_count = sum(1 for p in params if str(p.get("source")).lower() == "patent")
        return int((patent_count / len(params)) * 100)

    async def generate_recipes(self, cycle_id: uuid.UUID) -> list[RecipeCandidate]:
        cycle = await self.get_cycle(cycle_id)
        
        # Don't regenerate if already done
        if cycle.candidates:
            return cycle.candidates

        cycle.status = RecipeCycleStatus.GENERATING
        await self.session.commit()

        set_current_stage(TelemetryStage.RECIPE_GENERATION)
        set_current_operation("generate_recipes")

        prompt = RECIPE_GENERATION_SYSTEM_PROMPT.format(
            compound_name=cycle.compound_name,
            target_properties=json.dumps(cycle.target_properties, indent=2),
            competitor_data=json.dumps(cycle.competitor_data, indent=2),
            patent_context=json.dumps(cycle.patent_context_summary, indent=2)
        )

        try:
            # Enforce token budget mapping: 15K input / 4K output
            import tiktoken
            encoder = tiktoken.get_encoding("cl100k_base")
            while len(encoder.encode(prompt)) > 14000:
                # Trim patent context deterministically to stay within budget
                if cycle.patent_context_summary and "extracted_patents" in cycle.patent_context_summary and len(cycle.patent_context_summary["extracted_patents"]) > 0:
                    cycle.patent_context_summary["extracted_patents"].pop()
                    prompt = RECIPE_GENERATION_SYSTEM_PROMPT.format(
                        compound_name=cycle.compound_name,
                        target_properties=json.dumps(cycle.target_properties, indent=2),
                        competitor_data=json.dumps(cycle.competitor_data, indent=2),
                        patent_context=json.dumps(cycle.patent_context_summary, indent=2)
                    )
                else:
                    break

            parsed_data, raw_text, usage = await self.llm_client.generate_structured(
                prompt="Generate EXACTLY 5 recipe candidates based on the provided context. Do not generate more or less than 5.",
                system_prompt=prompt,
                schema=LLMRecipeSet,
                temperature=0.3
            )
            
            if not parsed_data:
                raise Exception("LLM returned empty structured data")

            recipes = parsed_data.recipes
            if len(recipes) != 5:
                # Should not happen with strict schema, but double check
                logger.warning("LLM did not return exactly 5 recipes. Count: %s", len(recipes))
            
            candidates = []
            for idx, r in enumerate(recipes[:5]):
                r_dict = r.model_dump()
                score = self._calculate_evidence_coverage(r_dict)
                cand = RecipeCandidate(
                    cycle_id=cycle.id,
                    rank=idx + 1,
                    name=r_dict.get("name", f"Recipe {idx + 1}"),
                    recipe_data=r_dict,
                    patent_references=r_dict.get("patent_references", []),
                    evidence_coverage_score=score
                )
                self.session.add(cand)
                candidates.append(cand)
                
            cycle.status = RecipeCycleStatus.STEP2
            await self.session.commit()
            
            for c in candidates:
                await self.session.refresh(c)
                
            return candidates

        except Exception as e:
            logger.error("Failed to generate recipes: %s", str(e))
            cycle.status = RecipeCycleStatus.FAILED
            await self.session.commit()
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"Recipe generation failed: {str(e)}")

    async def select_candidate(self, cycle_id: uuid.UUID, candidate_id: uuid.UUID) -> RecipeCycle:
        cycle = await self.get_cycle(cycle_id)
        
        # Mark all as false first
        for c in cycle.candidates:
            c.is_selected = False
            
        candidate = next((c for c in cycle.candidates if c.id == candidate_id), None)
        if not candidate:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Candidate not found")
            
        candidate.is_selected = True
        cycle.selected_candidate_id = candidate_id
        cycle.status = RecipeCycleStatus.STEP3
        await self.session.commit()
        await self.session.refresh(cycle)
        return cycle

    # ── Customer Trial Management ─────────────────────────────────────────────

    async def create_trial(self, data: CustomerTrialCreate, current_user: User) -> CustomerTrial:
        # Verify candidate exists
        candidate_result = await self.session.execute(
            select(RecipeCandidate).where(RecipeCandidate.id == data.selected_candidate_id)
        )
        candidate = candidate_result.scalar_one_or_none()
        if not candidate:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Selected candidate not found")
            
        trial = CustomerTrial(
            cycle_id=candidate.cycle_id,
            selected_candidate_id=candidate.id,
            created_by=current_user.id,
            feedback_text=data.feedback_text,
            actual_values=data.actual_values,
            target_values=data.target_values,
            status=TrialStatus.PENDING
        )
        self.session.add(trial)
        
        # Update cycle status if needed
        cycle = await self.session.get(RecipeCycle, candidate.cycle_id)
        if cycle:
            cycle.status = RecipeCycleStatus.STEP3
            
        await self.session.commit()
        await self.session.refresh(trial)
        return trial

    async def update_trial(self, trial_id: uuid.UUID, data: CustomerTrialUpdate) -> CustomerTrial:
        trial = await self.session.get(CustomerTrial, trial_id)
        if not trial:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Trial not found")
            
        if data.feedback_text is not None:
            trial.feedback_text = data.feedback_text
        if data.actual_values is not None:
            trial.actual_values = data.actual_values
        if data.target_values is not None:
            trial.target_values = data.target_values
            
        await self.session.commit()
        await self.session.refresh(trial)
        return trial

    # ── Optimization ──────────────────────────────────────────────────────────

    async def generate_optimized_recipes(self, trial_id: uuid.UUID) -> list[OptimizedRecipeCandidate]:
        result = await self.session.execute(
            select(CustomerTrial)
            .where(CustomerTrial.id == trial_id)
            .options(selectinload(CustomerTrial.optimized_candidates))
        )
        trial = result.scalar_one_or_none()
        if not trial:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Trial not found")
            
        if trial.optimized_candidates:
            return trial.optimized_candidates
            
        trial.status = TrialStatus.OPTIMIZING
        await self.session.commit()

        set_current_stage(TelemetryStage.RECIPE_OPTIMIZATION)
        set_current_operation("generate_optimization")

        candidate = await self.session.get(RecipeCandidate, trial.selected_candidate_id)
        cycle = await self.session.get(RecipeCycle, trial.cycle_id)

        prompt = RECIPE_OPTIMIZATION_SYSTEM_PROMPT.format(
            selected_recipe=json.dumps(candidate.recipe_data, indent=2),
            customer_feedback=trial.feedback_text or "No text feedback provided.",
            actual_vs_target=json.dumps({
                "actual": trial.actual_values,
                "target": trial.target_values
            }, indent=2),
            patent_context=json.dumps(cycle.patent_context_summary, indent=2)
        )

        try:
            # Enforce budget 10K input / 3K output
            import tiktoken
            encoder = tiktoken.get_encoding("cl100k_base")
            while len(encoder.encode(prompt)) > 9500:
                # Trim patent context deterministically to stay within budget
                if cycle.patent_context_summary and "extracted_patents" in cycle.patent_context_summary and len(cycle.patent_context_summary["extracted_patents"]) > 0:
                    cycle.patent_context_summary["extracted_patents"].pop()
                    prompt = RECIPE_OPTIMIZATION_SYSTEM_PROMPT.format(
                        selected_recipe=json.dumps(candidate.recipe_data, indent=2),
                        customer_feedback=trial.feedback_text or "No text feedback provided.",
                        actual_vs_target=json.dumps({
                            "actual": trial.actual_values,
                            "target": trial.target_values
                        }, indent=2),
                        patent_context=json.dumps(cycle.patent_context_summary, indent=2)
                    )
                else:
                    break

            parsed_data, raw_text, usage = await self.llm_client.generate_structured(
                prompt="Generate EXACTLY 3 revised recipes based on the feedback and provided context. Do not generate more or less than 3.",
                system_prompt=prompt,
                schema=LLMOptimizationSet,
                temperature=0.3
            )
            
            if not parsed_data:
                raise Exception("LLM returned empty structured data")
            
            optimized_recipes = parsed_data.optimized_recipes
            if len(optimized_recipes) != 3:
                logger.warning("LLM did not return exactly 3 optimized recipes. Count: %s", len(optimized_recipes))
            
            opts = []
            for r in optimized_recipes[:3]:
                r_dict = r.model_dump()
                opt = OptimizedRecipeCandidate(
                    trial_id=trial.id,
                    revision_label=r_dict.get("revision_label", "Rev"),
                    name=r_dict.get("name", "Optimized Recipe"),
                    recipe_data=r_dict,
                    changed_parameters=r_dict.get("changed_parameters", []),
                    predicted_impacts=r_dict.get("predicted_impacts", [])
                )
                self.session.add(opt)
                opts.append(opt)
                
            trial.status = TrialStatus.COMPLETED
            cycle.status = RecipeCycleStatus.STEP4
            await self.session.commit()
            
            for o in opts:
                await self.session.refresh(o)
                
            return opts

        except Exception as e:
            logger.error("Failed to generate optimized recipes: %s", str(e))
            trial.status = TrialStatus.FAILED
            await self.session.commit()
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"Optimization failed: {str(e)}")

    async def select_optimized(self, trial_id: uuid.UUID, optimized_id: uuid.UUID) -> CustomerTrial:
        result = await self.session.execute(
            select(CustomerTrial)
            .where(CustomerTrial.id == trial_id)
            .options(selectinload(CustomerTrial.optimized_candidates))
        )
        trial = result.scalar_one_or_none()
        if not trial:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Trial not found")
            
        for o in trial.optimized_candidates:
            o.is_selected = False
            
        opt = next((o for o in trial.optimized_candidates if o.id == optimized_id), None)
        if not opt:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Optimized candidate not found")
            
        opt.is_selected = True
        trial.selected_optimized_id = optimized_id
        
        cycle = await self.session.get(RecipeCycle, trial.cycle_id)
        if cycle:
            cycle.status = RecipeCycleStatus.COMPLETED
            
        await self.session.commit()
        await self.session.refresh(trial)
        return trial
