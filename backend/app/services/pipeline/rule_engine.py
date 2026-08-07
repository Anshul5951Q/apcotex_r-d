import re
import logging
from typing import Tuple, List
import yaml
import os

from app.services.pipeline.schemas import CompoundSearchProfile, EvidenceLedger, CandidateState

logger = logging.getLogger(__name__)

class RuleEngineService:
    def __init__(self):
        # Load YAML configuration
        config_path = os.path.join(os.path.dirname(__file__), "..", "..", "core", "filter_config.yaml")
        try:
            with open(config_path, "r") as f:
                self.config = yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Failed to load filter_config.yaml: {e}")
            self.config = {}
            
        self.obvious_false_positives = self.config.get("obvious_false_positives", [])

    def _normalize_text(self, text: str) -> str:
        """Strips hyphens, slashes, commas, and excessive spaces for normalized matching."""
        text = text.lower()
        text = re.sub(r'[-\/,_]', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def evaluate_candidate_metadata(self, metadata: dict, ledger: EvidenceLedger, profile: CompoundSearchProfile):
        """
        Progressive Qualification on Serper Metadata.
        Modifies ledger in-place.
        """
        title = metadata.get("title", "")
        snippet = metadata.get("snippet", "")
        raw_text = f"{title} {snippet}"
        text = self._normalize_text(raw_text)
        
        # Dimension E: Chemistry Consistency
        competing_count = 0
        for term in profile.competing_chemistry:
            norm_term = self._normalize_text(term)
            if norm_term in text:
                ledger.dimensions.competing_chemistry.append(term)
                ledger.log(f"Stage 2 (Consistency): Found competing chemistry '{term}'")
                competing_count += 1
                
        # Dimension A: Compound Evidence
        norm_compound = self._normalize_text(profile.compound_name)
        if norm_compound in text:
            ledger.dimensions.compound_evidence.append(profile.compound_name)
            ledger.log(f"Stage 2 (Compound): Exact match '{profile.compound_name}'")
            
        for syn in profile.synonyms + profile.abbreviations + profile.alternative_industry_names:
            norm_syn = self._normalize_text(syn)
            if norm_syn in text:
                ledger.dimensions.matched_synonyms.append(syn)
                ledger.log(f"Stage 2 (Compound): Synonym match '{syn}'")
                
        for monomer in profile.major_monomers:
            norm_monomer = self._normalize_text(monomer)
            if norm_monomer in text:
                ledger.dimensions.matched_monomers.append(monomer)
                ledger.log(f"Stage 2 (Compound): Monomer match '{monomer}'")
                
        norm_family = self._normalize_text(profile.chemical_family)
        if norm_family in text:
            ledger.dimensions.matched_chemistry_family.append(profile.chemical_family)
            ledger.log(f"Stage 2 (Compound): Family match '{profile.chemical_family}'")
            
        if not ledger.dimensions.has_compound_evidence:
            ledger.state = CandidateState.REJECTED
            ledger.rejection_reason = "No chemistry evidence"
            ledger.log("Rejected: No chemistry evidence found in metadata.")
            return

        # Demote if competing dominates and compound evidence is weak
        if competing_count > 0 and len(ledger.dimensions.matched_monomers) < 2 and not ledger.dimensions.compound_evidence:
            ledger.state = CandidateState.REJECTED
            ledger.rejection_reason = "Competing chemistry dominates"
            ledger.log("Rejected: Competing chemistry dominates without strong target compound evidence.")
            return

        # Dimension B: Manufacturing Evidence
        for term in profile.typical_manufacturing_keywords + profile.manufacturing_keywords + profile.typical_polymerization_routes:
            norm_term = self._normalize_text(term)
            if norm_term in text:
                ledger.dimensions.manufacturing_evidence.append(term)
                ledger.log(f"Stage 3 (Manufacturing): Found '{term}'")

        # Dimension D: Application Rejection
        for term in self.obvious_false_positives + profile.application_keywords:
            norm_term = self._normalize_text(term)
            if norm_term in text:
                ledger.dimensions.negative_evidence.append(term)
                ledger.log(f"Stage 5 (Application): Found negative signal '{term}'")
                
        # If application signals exist without ANY manufacturing signals, reject immediately
        if ledger.dimensions.negative_evidence and not ledger.dimensions.has_manufacturing_evidence:
             ledger.state = CandidateState.REJECTED
             ledger.rejection_reason = "Application patent"
             ledger.log("Rejected: Application patent with no manufacturing evidence.")
             return
             
        # Promote/Demote State based on Confidence
        total = ledger.dimensions.overall_confidence
        if total >= 80 and ledger.dimensions.has_compound_evidence:
            ledger.state = CandidateState.HIGH
            ledger.log(f"Promoted to HIGH (Score: {total})")
        elif total >= 40:
            ledger.state = CandidateState.MEDIUM
            ledger.log(f"Assigned to MEDIUM (Score: {total})")
        elif total >= 15:
            ledger.state = CandidateState.LOW
            ledger.log(f"Assigned to LOW (Score: {total})")
        else:
            ledger.state = CandidateState.REJECTED
            ledger.rejection_reason = "Low overall confidence"
            ledger.log(f"REJECTED (Score: {total})")
        
    def score_content(self, parsed_patent, profile: CompoundSearchProfile, ledger: EvidenceLedger):
        """
        Progressive Qualification on Deep HTML Content.
        Extracts structural Recipe Evidence.
        """
        abstract = (parsed_patent.abstract or "")
        description = (parsed_patent.detailed_description or "")
        claims = (parsed_patent.claims or "")
        examples = (parsed_patent.examples or "")
        raw_text = f"{abstract} {description} {claims} {examples}"
        text = self._normalize_text(raw_text)
        
        # Dimension C: Recipe Evidence
        recipe_keywords = ["temperature", "pressure", "phr", "parts by weight", "wt%", "dosage", "reactor", "conversion", "initiator", "reaction time", "feed", "latex", "solids content", "emulsifier", "coagulation", "yield"]
        
        for kw in recipe_keywords:
            if kw in text:
                if kw not in ledger.dimensions.recipe_evidence:
                    ledger.dimensions.recipe_evidence.append(kw)
                ledger.log(f"Stage 4 (Recipe): Structural evidence '{kw}' identified")
                
        if len(examples) > 100:
            ledger.dimensions.recipe_evidence.append("extensive experimental examples")
            ledger.log("Stage 4 (Recipe): High volume of Examples Found")
            
        if not ledger.dimensions.has_recipe_evidence:
            ledger.state = CandidateState.REJECTED
            ledger.rejection_reason = "Recipe absent"
            ledger.log("Rejected: No structural recipe evidence found in full document.")
            return
            
        ledger.log(f"Stage 6: Content structurally verified. Total Overall Confidence: {ledger.dimensions.overall_confidence}")
