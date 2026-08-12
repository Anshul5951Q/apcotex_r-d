import re
from typing import Tuple
from app.services.pipeline.schemas import CompoundSearchProfile
from app.models.search_result import TitleScreeningStatus

class TitleScorer:
    """
    Generic, production-focused title scoring engine.
    Scores based on production/polymerization intent vs downstream application intent.
    Works for any compound, not just NBR.
    """
    def __init__(self, profile: CompoundSearchProfile):
        self.profile = profile
        
        # Build keyword sets from profile
        self.target_material = [profile.compound_name.lower()] + [s.lower() for s in profile.synonyms]
        self.abbreviations = [a.lower() for a in profile.abbreviations] if profile.abbreviations else []
        self.monomers = [m.lower() for m in profile.major_monomers] if profile.major_monomers else []
        self.comp_keywords = [k.lower() for k in profile.target_composition_keywords] if profile.target_composition_keywords else []
        self.important_constraints = [c.lower() for c in profile.important_constraints] if profile.important_constraints else []
        
        # Production-focused terminology (generic, works for any compound)
        self.production_method_terms = [
            "method for producing", "method for preparing",
            "process for producing", "process for preparing",
            "method of producing", "method of preparing",
            "process of producing", "process of preparing"
        ]
        self.production_process_terms = [
            "polymerization", "polymerisation", "polymerizing",
            "preparation", "preparing", "production", "producing",
            "manufacturing", "synthesis", "synthesizing"
        ]
        self.production_recipe_terms = [
            "initiator", "emulsifier", "surfactant", "chain transfer",
            "monomer", "catalyst", "polymerization process",
            "manufacturing process", "preparation process"
        ]
        
        # Downstream application terms (from profile + generic)
        self.downstream_terms = [k.lower() for k in profile.application_keywords] if profile.application_keywords else []
        generic_downstream = [
            "hose", "seal", "tire", "glove", "coating", "adhesive",
            "battery", "electrode", "composite", "roofing", "door",
            "footwear", "automotive component", "article", "product",
            "vulcaniz", "compounding", "curing", "cross-linkable", "filler",
            "tread", "belt", "film", "sheet", "pipe", "tube"
        ]
        self.downstream_terms = list(set(self.downstream_terms + generic_downstream))
        
        # Wrong materials (from profile)
        self.wrong_materials = [c.lower() for c in profile.competing_chemistry] if profile.competing_chemistry else []

    def _contains_any(self, text: str, keywords: list[str]) -> bool:
        text_lower = text.lower()
        for kw in keywords:
            if kw in text_lower:
                return True
        return False

    def _contains_all(self, text: str, keywords: list[str]) -> bool:
        text_lower = text.lower()
        if not keywords: return False
        for kw in keywords:
            if kw not in text_lower:
                return False
        return False

    def _contains_phrase(self, text: str, phrase: str) -> bool:
        """Check if a multi-word phrase is in the text."""
        return phrase.lower() in text.lower()

    def score_title(self, title: str) -> Tuple[int, TitleScreeningStatus, dict]:
        score = 0
        signals = {}
        exclusion_reason = None
        title_lower = title.lower()
        
        # === PRODUCTION INTENT SCORING (Positive) ===
        
        # Strong production method phrases (highest weight)
        for phrase in self.production_method_terms:
            if self._contains_phrase(title, phrase):
                score += 50
                signals["production_method_phrase"] = 50
                break
        
        # Production process terms
        if self._contains_any(title, self.production_process_terms):
            score += 40
            signals["production_process_term"] = 40
        
        # Recipe/technical terms
        if self._contains_any(title, self.production_recipe_terms):
            score += 30
            signals["recipe_terminology"] = 30
        
        # "and method for producing the same" pattern
        if "and method for producing the same" in title_lower or "and method for preparing the same" in title_lower:
            score += 30
            signals["method_for_producing_same"] = 30
        
        # === TARGET COMPOUND MATCHING ===
        
        target_match = False
        target_match_score = 0
        
        # Exact target material match
        if self._contains_any(title, self.target_material):
            target_match = True
            target_match_score = 50
            score += 50
            signals["target_material_match"] = 50
        # Abbreviation match
        elif self._contains_any(title, self.abbreviations):
            target_match = True
            target_match_score = 30
            score += 30
            signals["abbreviation_match"] = 30
        # All monomers present (strong indicator)
        elif self.monomers and self._contains_all(title, self.monomers):
            target_match = True
            target_match_score = 25
            score += 25
            signals["all_monomers_present"] = 25
        # Some monomers present (weaker)
        elif self.monomers:
            monomer_count = sum(1 for m in self.monomers if m in title_lower)
            if monomer_count >= len(self.monomers) / 2:
                target_match = True
                target_match_score = 15
                score += 15
                signals["partial_monomers_present"] = 15
        
        signals["target_match"] = target_match
        
        # Important constraints (e.g., "low acrylonitrile")
        if self.important_constraints and self._contains_any(title, self.important_constraints):
            score += 20
            signals["constraint_match"] = 20
        
        # Composition keywords (e.g., "low ACN")
        if self.comp_keywords and self._contains_any(title, self.comp_keywords):
            score += 15
            signals["composition_keyword_match"] = 15
        
        # === DOWNSTREAM APPLICATION SCORING (Negative) ===
        
        # Downstream application terms (strong rejection)
        if self._contains_any(title, self.downstream_terms):
            score -= 70
            signals["downstream_application"] = -70
            exclusion_reason = "Downstream application patent excluded"
        
        # Wrong materials (strong rejection)
        if self._contains_any(title, self.wrong_materials):
            score -= 50
            signals["wrong_material"] = -50
            if not exclusion_reason:
                exclusion_reason = "Competing/wrong material excluded"
        
        # === CRITICAL: TARGET MATCH IS MANDATORY FOR STRONG/ACCEPTED ===
        # If no target match, reject regardless of production intent
        if not target_match:
            status = TitleScreeningStatus.REJECT
            signals["rejection_reason"] = "No target compound match"
            if not exclusion_reason:
                exclusion_reason = "No target compound match"
        elif exclusion_reason:
            # Has target match but has exclusion reason (downstream/wrong material)
            status = TitleScreeningStatus.REJECT
        # === CLASSIFICATION (only if target match exists) ===
        elif score >= 80:
            status = TitleScreeningStatus.STRONG
        elif score >= 50:
            status = TitleScreeningStatus.MEDIUM
        elif score >= 20:
            status = TitleScreeningStatus.WEAK
        else:
            status = TitleScreeningStatus.REJECT
        
        # Add exclusion reason to signals if applicable
        if exclusion_reason:
            signals["exclusion_reason"] = exclusion_reason
        
        # Add intent classification to signals
        if not target_match:
            signals["intent_classification"] = "WRONG_COMPOUND"
        elif exclusion_reason:
            signals["intent_classification"] = "DOWNSTREAM/UNRELATED"
        elif score >= 50:
            signals["intent_classification"] = "PRODUCTION/POLYMERIZATION"
        elif score >= 20:
            signals["intent_classification"] = "POSSIBLE_PRODUCTION"
        else:
            signals["intent_classification"] = "UNCERTAIN"
        
        return score, status, signals
