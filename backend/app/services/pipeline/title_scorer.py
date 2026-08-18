"""
app/services/pipeline/title_scorer.py

Deterministic relevance scorer for patent title screening.

TWO-STAGE ARCHITECTURE:
  Stage 1 — Title Screen:
    A. Target Material Match (dynamic from profile)
    B. Synthesis/Preparation Match (generic + profile-derived)
    C. Downstream Subject Detection (hard-reject primary application subjects)

  Stage 2 — Content Verification (for ambiguous generic polymer titles):
    Deterministically checks fetched patent content for target-polymer
    polymerization evidence. No LLM call.

DECISION:
  ACCEPT       — direct target polymer synthesis title
  GENERIC_VERIFY — generic polymer title, requires content check
  REJECTED     — application/downstream subject, no synthesis, or exclusion
"""
import logging
import re
from typing import List, Tuple, Dict, Any, Optional
from dataclasses import dataclass

from app.services.pipeline.schemas import CompoundSearchProfile
from app.models.search_result import TitleScreeningStatus

logger = logging.getLogger(__name__)

@dataclass
class ContentValidationResult:
    material_match: bool
    material_evidence: str
    target_identity_evidence: str
    precursor_evidence: str
    transformation_evidence: str
    synthesis_match: bool
    synthesis_evidence: str
    attribute_required: bool
    attribute_match: str  # 'MATCH', 'NO_MATCH', 'UNCERTAIN', 'NOT_REQUIRED'
    attribute_evidence: str
    final_decision: str   # 'ACCEPT', 'REJECT', 'UNCERTAIN'
    rejection_reason: str
    formulation_only: bool = False
    downstream_only: bool = False
    background_only: bool = False
    precursor_only: bool = False

TIER_ACCEPT = "ACCEPT"
TIER_GENERIC_VERIFY = "GENERIC_VERIFY"  # ambiguous title, pass to content check
TIER_REJECTED = "REJECTED"

# ─────────────────────────────────────────────────────────────
# SYNTHESIS TERMS — universal process concepts, NOT chemistry-specific
# ─────────────────────────────────────────────────────────────
_GENERIC_SYNTHESIS_TERMS = [
    "polymerization", "polymerisation",
    "copolymerization", "copolymerisation",
    "emulsion polymerization", "emulsion polymerisation",
    "free radical polymerization",
    "synthesis", "synthesizing", "synthesising",
    "preparation", "preparing",
    "production", "producing",
    "manufacturing", "manufacture",
    "process for preparing", "process for producing",
    "method for preparing", "method for producing",
    "method of preparing", "method of producing",
    "method for manufacturing", "method of manufacturing",
    "process for manufacturing",
    "polymer production",
]

# Terms that indicate synthesis context WITHOUT the word "process" or "method"
# (short verbs/nouns we allow only when combined with a material match)
_SYNTHESIS_SUPPORTING_TERMS = [
    "process", "method",
]

# ─────────────────────────────────────────────────────────────
# HARD DOWNSTREAM SUBJECTS
# These represent end-use applications; if the title's PRIMARY subject
# is one of these, the patent is rejected regardless of material match.
# These are ordered longest-first so partial matches don't shadow longer ones.
# ─────────────────────────────────────────────────────────────
_HARD_DOWNSTREAM_SUBJECTS = [
    # Energy / electronics
    "secondary battery", "lithium battery", "lithium-ion battery",
    "lead acid battery", "fuel cell", "solar cell",
    "positive electrode", "negative electrode", "electrode material",
    "electrode composition", "electrode binder", "electrode active material",
    "separator membrane", "solid electrolyte", "composite electrolyte",
    "conductive layer", "conductive member", "conductive film",
    "electrophotographic member", "electrophotographic photoreceptor",
    "process cartridge", "image forming apparatus", "image forming device",
    "toner", "developer", "charge roller",
    "capacitor",
    # Tires and seals
    "pneumatic tire", "pneumatic tyre", "run-flat tire",
    "tire tread", "tyre tread", "tire cord",
    # Medical / consumer
    "surgical glove", "examination glove", "medical glove",
    "medical device", "medical tube",
    "condom",
    # Industrial application products
    "fuel hose", "hydraulic hose", "oil hose",
    "o-ring", "gasket", "shaft seal", "oil seal", "lip seal",
    "vibration isolator", "vibration damper",
    "conveyor belt", "drive belt", "transmission belt",
    "diaphragm pump", "membrane pump",
    # Composites / coatings / adhesives
    "fiber reinforced", "fibre reinforced",
    "carbon fiber composite", "carbon fibre composite",
    "epoxy composite", "laminated sheet",
    "coating composition", "coating agent",
    "paint composition", "primer composition",
    "adhesive composition", "pressure sensitive adhesive",
    # Rubber compounding / downstream formulation
    "vulcanized rubber composition", "vulcanized rubber compound",
    "rubber composition for", "rubber compound for",
    "rubber article", "rubber molded article", "molded rubber article",
    "vulcanizate", "crosslinked rubber",
    "foam rubber", "sponge rubber",
    "oil extended rubber", "oil-extended rubber",
    # Recycling / regeneration
    "rubber recycling", "rubber regeneration", "devulcanization",
    "reclaimed rubber", "recycled rubber", "pyrolysis",
    "waste rubber",
    # Miscellaneous application subjects
    "oilfield application", "drilling fluid", "spacer fluid",
    "well cement", "cement composition",
    "binder composition", "paper binder",
    "soil improvement", "soil amendment",
    "leather treatment",
    "food packaging", "packaging material",
    "flame retardant composition",
    "shoe sole", "footwear",
    "airbag",
]

# ─────────────────────────────────────────────────────────────
# SOFT DOWNSTREAM INDICATORS
# These are lower-confidence downstream signals. A title containing
# ONLY one of these (no strong synthesis match, no strong material match)
# will be rejected. But if a strong synthesis term is also present,
# we allow the title through to GENERIC_VERIFY.
# ─────────────────────────────────────────────────────────────
_SOFT_DOWNSTREAM_TERMS = [
    "tire", "tyre",
    "glove",
    "battery", "electrode", "separator",
    "photoreceptor", "photosensitive",
    "hose",
    "membrane",
    "film", "coating", "paint",
    "adhesive",
    "gasket", "seal", "sealing",
    "dielectric",
    "binder",
    "masterbatch",
    "recycling", "regeneration",
]

# ─────────────────────────────────────────────────────────────
# ROLE INDICATOR PHRASES
# These phrases in a title confirm the material is used AS A COMPONENT,
# not the subject of synthesis.
# ─────────────────────────────────────────────────────────────
_FORMULATION_COMPONENT_PHRASES = [
    " comprising ", " containing ", " including ", " using ",
    " based on ", " incorporated into ", " added to ", " blended with ",
    " mixed with ", " reinforced with ", " filled with ",
    " rubber compound comprising", " composition comprising",
    " formulation comprising",
]


class CandidateScorer:
    """
    Dynamic two-stage title-first candidate scoring engine
    driven by CompoundSearchProfile.

    Stage 1: Title screening
    Stage 2: (Separate) Content verification for GENERIC_VERIFY tier.
    """

    def __init__(self, profile: CompoundSearchProfile):
        self.profile = profile

        def _norm(s: str) -> str:
            return re.sub(r'[-\s]+', ' ', s.lower().strip()) if s else ""

        # ── A. Target Material Terms ──────────────────────────────────────────
        exact_subjects = [_norm(profile.base_chemistry), _norm(profile.compound_name)]
        synonyms = [_norm(s) for s in profile.synonyms]
        abbreviations = [_norm(a) for a in getattr(profile, "abbreviations", [])]
        aliases = [_norm(a) for a in getattr(profile, "material_aliases", [])]
        raw_material = [x for x in (exact_subjects + synonyms + abbreviations + aliases) if len(x) > 2]
        # Sort longest-first to avoid partial-match shadowing
        self.all_material_terms = sorted(set(raw_material), key=len, reverse=True)

        # ── Precursors and Transformations (for precursor-based material match) ──
        precursors = [_norm(p) for p in getattr(profile, "precursor_terms", [])]
        transformations = [_norm(t) for t in getattr(profile, "transformation_terms", [])]
        self.precursor_terms = sorted(set([x for x in precursors if len(x) > 2]), key=len, reverse=True)
        self.transformation_terms = sorted(set([x for x in transformations if len(x) > 2]), key=len, reverse=True)

        # ── B. Synthesis Terms ────────────────────────────────────────────────
        raw_synth = (
            [t.lower() for t in getattr(profile, "synthesis_terms", [])]
            + [t.lower() for t in getattr(profile, "typical_polymerization_routes", [])]
        )
        # Merge profile-derived + generic, longest-first
        all_synth = list(set([x for x in raw_synth if x]
                              + _GENERIC_SYNTHESIS_TERMS
                              + _SYNTHESIS_SUPPORTING_TERMS))
        self.synthesis_terms = sorted(all_synth, key=len, reverse=True)

        # ── C. Strong synthesis terms (subset — unambiguous synthesis verbs) ──
        self.strong_synthesis_terms = sorted(
            [x for x in all_synth if x not in _SYNTHESIS_SUPPORTING_TERMS],
            key=len, reverse=True
        )

        # ── D. Target Attribute Terms (for bonus scoring) ─────────────────────
        axis_c_terms: list[str] = []
        for attr in getattr(profile, "target_attributes", []):
            axis_c_terms.extend([t.lower() for t in getattr(attr, "terms", [])])
        axis_c_terms.extend([t.lower() for t in getattr(profile, "target_composition_keywords", [])])
        axis_c_terms.extend([t.lower() for t in getattr(profile, "important_constraints", [])])
        self.axis_c_terms = [t for t in axis_c_terms if len(t) > 3]

        # ── E. Exclusion Terms (hard chemistry mismatches from profile) ────────
        profile_exclusions = [t.lower() for t in getattr(profile, "exclusion_concepts", [])]
        profile_derivatives = [t.lower() for t in getattr(profile, "derivative_exclusion_terms", [])]
        competing = [t.lower() for t in getattr(profile, "competing_chemistry", [])]
        self.exclusion_terms = sorted(
            set(profile_exclusions + profile_derivatives + competing),
            key=len, reverse=True
        )

        # ── F. Downstream Terms (profile-derived + hardcoded) ─────────────────
        profile_app = [t.lower() for t in getattr(profile, "application_keywords", [])]
        profile_downstream = [t.lower() for t in getattr(profile, "downstream_application_terms", [])]
        self.hard_downstream = sorted(
            set([t.lower() for t in _HARD_DOWNSTREAM_SUBJECTS] + profile_app + profile_downstream),
            key=len, reverse=True
        )
        self.soft_downstream = sorted(
            set([t.lower() for t in _SOFT_DOWNSTREAM_TERMS]),
            key=len, reverse=True
        )

        # (Removed hardcoded major_monomers in favor of precursor_terms + transformation_terms)

    # ─────────────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _find_match(self, text: str, keywords: list) -> str:
        """Return the first keyword that appears as a substring in text."""
        if not text or not keywords:
            return ""
        text_lower = text.lower()
        for kw in keywords:
            if kw.strip() and kw.strip() in text_lower:
                return kw.strip()
        return ""

    def _strip_material_from_title(self, title_lower: str) -> str:
        """Remove all known material terms from the title so we can check what remains."""
        cleaned = title_lower
        for mat in self.all_material_terms:
            cleaned = cleaned.replace(mat, " ")
        return cleaned

    def _contains_formulation_role(self, title_lower: str) -> str:
        """
        Detect phrases that indicate the target material is only USED as a
        component in a formulation, not synthesized.
        """
        for phrase in _FORMULATION_COMPONENT_PHRASES:
            if phrase in title_lower:
                return phrase.strip()
        return ""

    def _is_primary_downstream_subject(self, title_lower: str) -> str:
        """
        Determine if the title's primary subject is a downstream application.

        Logic:
        1. Strip the material terms from the title.
        2. Check if a hard downstream subject appears in what remains.
        3. If the downstream subject is the FIRST substantive noun in the remaining
           title, it is the primary subject → reject.
        4. Additionally, any title where a hard downstream word appears BEFORE
           the matched material term is also a primary-downstream title.
        """
        matched_material = self._find_match(title_lower, self.all_material_terms)
        idx_mat = title_lower.find(matched_material) if matched_material else len(title_lower)

        # Check hard downstream terms
        for ds_term in self.hard_downstream:
            if ds_term in title_lower:
                idx_ds = title_lower.find(ds_term)
                # Reject if downstream appears BEFORE material, OR if material is
                # not present at all (the title is purely an application title)
                if not matched_material or idx_ds < idx_mat:
                    return ds_term
                # Also reject when the title matches a hard downstream subject that
                # appears AFTER the material but there's no unambiguous synthesis term
                # (e.g., "NBR rubber composition for batteries")
                stripped = self._strip_material_from_title(title_lower)
                if self._find_match(stripped, self.hard_downstream):
                    # Only reject if there is no strong synthesis term in the full title
                    if not self._find_match(title_lower, self.strong_synthesis_terms):
                        return ds_term

        return ""

    # ─────────────────────────────────────────────────────────────────────────
    # Stage 1 — Title Screen
    # ─────────────────────────────────────────────────────────────────────────

    def score_candidate_tiered(
        self, title: str, snippet: str, source_query: str
    ) -> tuple[int, str, dict]:
        """
        Stage 1 title screening.

        Returns (score, tier, signals) where tier ∈ {ACCEPT, GENERIC_VERIFY, REJECTED}

        ACCEPT         — title directly confirms target material + synthesis
        GENERIC_VERIFY — title is a plausible generic polymer synthesis title
                         requiring deterministic content verification
        REJECTED       — application/downstream subject, missing synthesis, or
                         explicit exclusion
        """
        title_lower = (title or "").lower().strip()
        snippet_lower = (snippet or "").lower()

        signals: dict = {
            "matched_material": "",
            "matched_synthesis": "",
            "matched_downstream": "",
            "matched_attribute": "",
            "matched_exclusion": "",
            "axis_a": 0,
            "axis_b": 0,
            "axis_c": 0,
            "app_penalty": 0,
            "rejection_reason": "",
            "tier": TIER_REJECTED,
        }

        # ── Guard: skip empty titles ──
        if not title_lower:
            signals["rejection_reason"] = "REJECTED — empty title"
            return 0, TIER_REJECTED, signals

        # ── 1. Exclusion check (unrelated chemistry) ──────────────────────────
        exclusion_match = self._find_match(title_lower, self.exclusion_terms)
        if exclusion_match:
            signals["matched_exclusion"] = exclusion_match
            signals["rejection_reason"] = f"REJECTED — chemistry exclusion: {exclusion_match}"
            return 0, TIER_REJECTED, signals

        # ── 2. Primary downstream subject check ──────────────────────────────
        downstream_subject = self._is_primary_downstream_subject(title_lower)
        if downstream_subject:
            signals["matched_downstream"] = downstream_subject
            signals["rejection_reason"] = f"REJECTED — downstream application subject: {downstream_subject}"
            return 0, TIER_REJECTED, signals

        # ── 3. Formulation component role check ──────────────────────────────
        # If the title structure shows the material is USED (not synthesized),
        # reject unless a strong synthesis term overrides it.
        formulation_phrase = self._contains_formulation_role(title_lower)
        if formulation_phrase:
            # Allow only if a strong synthesis term explicitly appears
            strong_synth = self._find_match(title_lower, self.strong_synthesis_terms)
            if not strong_synth:
                signals["rejection_reason"] = (
                    f"REJECTED — target material only used as formulation component "
                    f"('{formulation_phrase}')"
                )
                return 0, TIER_REJECTED, signals

        # ── 4. Target material match ──────────────────────────────────────────
        matched_material = self._find_match(title_lower, self.all_material_terms)
        if matched_material:
            signals["matched_material"] = matched_material
            signals["axis_a"] = 50

        # ── 5. Synthesis term match ──────────────────────────────────────────
        matched_synthesis = self._find_match(title_lower, self.synthesis_terms)
        if matched_synthesis:
            signals["matched_synthesis"] = matched_synthesis
            # Strong synthesis terms (polymerization, preparation, etc.) score higher
            is_strong = matched_synthesis in self.strong_synthesis_terms
            signals["axis_b"] = 40 if is_strong else 20

        # ── 6. Target attribute bonus ────────────────────────────────────────
        matched_attribute = self._find_match(title_lower, self.axis_c_terms)
        if not matched_attribute:
            matched_attribute = self._find_match(snippet_lower, self.axis_c_terms)
        if matched_attribute:
            signals["matched_attribute"] = matched_attribute
            signals["axis_c"] = 20

        # ── 7. Soft downstream signal check ──────────────────────────────────
        # If a soft downstream word is present and there's no strong synthesis term,
        # apply a substantial penalty.
        soft_ds = self._find_match(title_lower, self.soft_downstream)
        if soft_ds:
            strong_synth = self._find_match(title_lower, self.strong_synthesis_terms)
            if not strong_synth:
                signals["app_penalty"] += 40
                signals["matched_downstream"] = soft_ds

        # ── 8. Compute total ──────────────────────────────────────────────────
        total = signals["axis_a"] + signals["axis_b"] + signals["axis_c"] - signals["app_penalty"]
        signals["total_score"] = total

        # ── 9. Decision logic ─────────────────────────────────────────────────
        has_material = bool(signals["matched_material"])
        has_strong_synth = bool(self._find_match(title_lower, self.strong_synthesis_terms))
        has_weak_synth = bool(signals["matched_synthesis"])

        # Precursor + Transformation-level material detection:
        # If a precursor AND a transformation term appear in the title,
        # treat it as a material match (e.g., "hydrogenation of nitrile rubber")
        if not has_material and self.precursor_terms and self.transformation_terms:
            precursor_hits = [p for p in self.precursor_terms if p in title_lower]
            transformation_hits = [t for t in self.transformation_terms if t in title_lower]
            
            if precursor_hits and transformation_hits:
                has_material = True
                signals["matched_material"] = f"precursor:{precursor_hits[0]}|transform:{transformation_hits[0]}"
                signals["axis_a"] = 40  # slightly lower than direct name match


        # Target evidence requires either material identity OR explicit target attribute match
        has_target_evidence = has_material or bool(signals.get("matched_attribute"))

        if not has_target_evidence and has_strong_synth:
            # Generic polymer synthesis title WITHOUT any target concept evidence
            signals["rejection_reason"] = "REJECTED — generic synthesis without target evidence"
            signals["tier"] = TIER_REJECTED
            return total, TIER_REJECTED, signals

        if has_target_evidence:
            if signals["app_penalty"] > 0:
                # Soft downstream detected. Only save it if strong synthesis is present
                if has_strong_synth:
                    signals["tier"] = TIER_GENERIC_VERIFY
                    signals["rejection_reason"] = ""
                    return max(total, 10), TIER_GENERIC_VERIFY, signals
                else:
                    signals["rejection_reason"] = f"REJECTED — Soft downstream application ({signals.get('matched_downstream', 'unknown')}) with no synthesis evidence"
                    signals["tier"] = TIER_REJECTED
                    return 0, TIER_REJECTED, signals
            else:
                # No downstream penalty. Target evidence is enough to make it a candidate.
                if has_material:
                    signals["tier"] = TIER_ACCEPT
                    signals["rejection_reason"] = ""
                    return total, TIER_ACCEPT, signals
                else:
                    # Attribute match without direct material name
                    signals["tier"] = TIER_GENERIC_VERIFY
                    signals["rejection_reason"] = ""
                    return max(total, 10), TIER_GENERIC_VERIFY, signals

        # All other cases: REJECT
        if not signals["rejection_reason"]:
            signals["rejection_reason"] = "REJECTED — target evidence (material or attribute) not established in title"
        
        signals["tier"] = TIER_REJECTED
        return total, TIER_REJECTED, signals

    # ─────────────────────────────────────────────────────────────────────────
    # Stage 2 — Content Verification (deterministic, zero LLM)
    # ─────────────────────────────────────────────────────────────────────────

    def verify_content(self, parsed_patent, profile: CompoundSearchProfile) -> 'ContentValidationResult':
        """
        Stage 2: Deterministically verify that a GENERIC_VERIFY candidate
        actually describes the polymerization/preparation of the target polymer,
        and matches target attributes within the same context block.
        """
        if parsed_patent is None:
            return ContentValidationResult(
                material_match=False, material_evidence="",
                target_identity_evidence="", precursor_evidence="", transformation_evidence="",
                synthesis_match=False, synthesis_evidence="",
                attribute_required=False, attribute_match="NOT_REQUIRED", attribute_evidence="",
                final_decision="REJECT", rejection_reason="REJECTED — content fetch failed"
            )

        # Build searchable text corpus (abstract first, then claims, then description)
        corpus_parts = []
        abstract = getattr(parsed_patent, "abstract", "") or ""
        claims = getattr(parsed_patent, "claims", "") or ""
        description = getattr(parsed_patent, "detailed_description", "") or ""
        examples = getattr(parsed_patent, "examples", "") or ""

        corpus_parts.append(abstract[:3000])
        corpus_parts.append(claims[:2000])
        corpus_parts.append(description[:3000])
        corpus_parts.append(examples[:2000])

        corpus = "\n".join(corpus_parts).lower()

        # Gather target monomer/material signals from profile
        material_terms = [t.lower() for t in (
            [profile.base_chemistry, profile.compound_name]
            + profile.synonyms
            + getattr(profile, "abbreviations", [])
        ) if t]

        synth_terms = [t.lower() for t in (
            getattr(profile, "synthesis_terms", [])
            + getattr(profile, "typical_polymerization_routes", [])
        )] + _GENERIC_SYNTHESIS_TERMS

        # Check 1: Target material appears in content (direct name match)
        mat_hit = self._find_match(corpus, material_terms)

        # Fallback 1: Precursor + Transformation appear in content
        # (patent says "hydrogenation" AND "nitrile rubber" —
        #  that's sufficient evidence the target polymer is discussed)
        precursor_hit = False
        if not mat_hit and self.precursor_terms and self.transformation_terms:
            precursors_in_corpus = [p for p in self.precursor_terms if p in corpus]
            transformations_in_corpus = [t for t in self.transformation_terms if t in corpus]
            if precursors_in_corpus and transformations_in_corpus:
                precursor_hit = True
                mat_hit = f"precursor:{precursors_in_corpus[0]}|transform:{transformations_in_corpus[0]}"

        if not mat_hit:
            return ContentValidationResult(
                material_match=False, material_evidence="",
                target_identity_evidence="", precursor_evidence="", transformation_evidence="",
                synthesis_match=False, synthesis_evidence="",
                attribute_required=False, attribute_match="NOT_REQUIRED", attribute_evidence="",
                final_decision="REJECT", rejection_reason="REJECTED — target material not established in content"
            )

        # Check 2: Synthesis/polymerization context found in content
        synth_hit = self._find_match(corpus, synth_terms)
        if not synth_hit:
            target_identity_evidence = str(mat_hit) if mat_hit and not precursor_hit else ""
            prec_ev = str(precursors_in_corpus[0]) if precursor_hit else ""
            trans_ev = str(transformations_in_corpus[0]) if precursor_hit else ""
            return ContentValidationResult(
                material_match=True, material_evidence=str(mat_hit),
                target_identity_evidence=target_identity_evidence, precursor_evidence=prec_ev, transformation_evidence=trans_ev,
                synthesis_match=False, synthesis_evidence="",
                attribute_required=False, attribute_match="NOT_REQUIRED", attribute_evidence="",
                final_decision="REJECT", rejection_reason="REJECTED — synthesis/preparation not described in content"
            )

        # Check 3: Short-corpus check for material and synthesis
        short_corpus = corpus[:4000]
        has_mat_short = bool(self._find_match(short_corpus, material_terms))
        if not has_mat_short and precursor_hit:
            has_precursor_short = bool(self._find_match(short_corpus, self.precursor_terms))
            has_transform_short = bool(self._find_match(short_corpus, self.transformation_terms))
            has_mat_short = has_precursor_short and has_transform_short
        has_synth_short = bool(self._find_match(short_corpus, synth_terms))
        
        # We don't auto-reject on short corpus failure immediately if attributes are present.
        # We'll evaluate attributes first.

        # Check 4: Target Attributes
        target_attrs = getattr(profile, "target_attributes", [])
        attr_required = len(target_attrs) > 0
        attr_match = "NOT_REQUIRED"
        attr_evidence = ""
        
        if attr_required:
            import re
            attr_match = "NO_MATCH"
            # Split corpus into paragraphs/blocks for contextual proximity
            blocks = re.split(r'\n\n|\.\s+', corpus)
            
            for block in blocks:
                # Is the material or synthesis in this block?
                block_has_mat = bool(self._find_match(block, material_terms))
                if not block_has_mat and precursor_hit:
                    block_has_mat = bool(self._find_match(block, self.precursor_terms)) and bool(self._find_match(block, self.transformation_terms))
                block_has_synth = bool(self._find_match(block, synth_terms))
                
                if block_has_mat or block_has_synth:
                    # Check if any target attribute is also in this block
                    for attr_model in target_attrs:
                        # Depending on structure, it could be a dict or a BaseModel
                        if isinstance(attr_model, dict):
                            attr_name = attr_model.get("name", "")
                            attr_cond = attr_model.get("condition", "")
                            attr_terms = attr_model.get("terms", [])
                        else:
                            attr_name = getattr(attr_model, "name", "")
                            attr_cond = getattr(attr_model, "condition", "")
                            attr_terms = getattr(attr_model, "terms", [])
                            
                        attr = f"{attr_name} {attr_cond} {' '.join(attr_terms)}".strip()
                        attr_lower = attr.lower()
                        
                        # Numeric range extraction
                        nums = re.findall(r'(\d+\.?\d*)', attr_lower)
                        if nums:
                            # If it's a numeric attribute, look for numbers in the block
                            block_nums = re.findall(r'(\d+\.?\d*)', block)
                            if block_nums:
                                # We just check if ANY number overlaps or is present
                                attr_match = "MATCH"
                                attr_evidence = f"numeric_overlap_in_context: {attr} -> {block[:100]}..."
                                break
                        else:
                            # Plain text attribute match using the terms
                            found_term = False
                            for term in attr_terms + [attr_name]:
                                if term and term.lower() in block:
                                    attr_match = "MATCH"
                                    attr_evidence = f"contextual_match: {term} -> {block[:100]}..."
                                    found_term = True
                                    break
                            if found_term:
                                break
                if attr_match == "MATCH":
                    break
                    
            if attr_match == "NO_MATCH":
                # Check if it appears anywhere at all (ambiguous)
                for attr_model in target_attrs:
                    if isinstance(attr_model, dict):
                        terms = attr_model.get("terms", []) + [attr_model.get("name", "")]
                    else:
                        terms = getattr(attr_model, "terms", []) + [getattr(attr_model, "name", "")]
                    for term in terms:
                        if term and term.lower() in corpus:
                            attr_match = "UNCERTAIN"
                            attr_evidence = f"attribute_found_outside_context: {term}"
                            break
                    if attr_match == "UNCERTAIN":
                        break
        
        # Define the basic evidence strings
        target_identity_evidence = str(mat_hit) if mat_hit and not precursor_hit else ""
        prec_ev = str(precursors_in_corpus[0]) if precursor_hit else ""
        trans_ev = str(transformations_in_corpus[0]) if precursor_hit else ""

        # Compute Flags
        is_precursor_only = bool(self._find_match(short_corpus, self.precursor_terms)) and not has_mat_short
        is_downstream_only = bool(self._is_primary_downstream_subject(abstract)) or bool(self._find_match(abstract, self.hard_downstream))
        is_formulation_only = bool(self._contains_formulation_role(abstract)) and not has_synth_short
        is_background_only = "background" in abstract.lower() and has_mat_short and not has_synth_short

        # Helper to inject flags
        def _with_flags(res: ContentValidationResult) -> ContentValidationResult:
            res.precursor_only = is_precursor_only
            res.downstream_only = is_downstream_only
            res.formulation_only = is_formulation_only
            res.background_only = is_background_only
            return res

        # Downstream/Formulation strict reject if there's no strong synthesis in abstract
        strong_synth_in_abstract = bool(self._find_match(abstract, self.strong_synthesis_terms))
        if (is_downstream_only or is_formulation_only) and not strong_synth_in_abstract:
            return _with_flags(ContentValidationResult(
                material_match=True, material_evidence=str(mat_hit),
                target_identity_evidence=target_identity_evidence, precursor_evidence=prec_ev, transformation_evidence=trans_ev,
                synthesis_match=False, synthesis_evidence="",
                attribute_required=attr_required, attribute_match=attr_match, attribute_evidence=attr_evidence,
                final_decision="REJECT", rejection_reason="REJECTED — target material used as formulation/downstream component, not synthesized"
            ))

        # Decision Logic
        if not (has_mat_short and has_synth_short):
            # Failed primary short-corpus check
            if attr_match == "MATCH" or attr_match == "UNCERTAIN":
                # But it has attribute evidence somewhere -> UNCERTAIN
                return _with_flags(ContentValidationResult(
                    material_match=True, material_evidence=str(mat_hit),
                    target_identity_evidence=target_identity_evidence, precursor_evidence=prec_ev, transformation_evidence=trans_ev,
                    synthesis_match=True, synthesis_evidence=str(synth_hit),
                    attribute_required=attr_required, attribute_match=attr_match, attribute_evidence=attr_evidence,
                    final_decision="UNCERTAIN", rejection_reason="UNCERTAIN — material/synthesis absent from abstract, but attributes found"
                ))
            else:
                return _with_flags(ContentValidationResult(
                    material_match=True, material_evidence=str(mat_hit),
                    target_identity_evidence=target_identity_evidence, precursor_evidence=prec_ev, transformation_evidence=trans_ev,
                    synthesis_match=True, synthesis_evidence=str(synth_hit),
                    attribute_required=attr_required, attribute_match=attr_match, attribute_evidence=attr_evidence,
                    final_decision="REJECT", rejection_reason="REJECTED — target polymer synthesis not confirmed in abstract/claims"
                ))

        if attr_required:
            if attr_match == "MATCH":
                return _with_flags(ContentValidationResult(
                    material_match=True, material_evidence=str(mat_hit),
                    target_identity_evidence=target_identity_evidence, precursor_evidence=prec_ev, transformation_evidence=trans_ev,
                    synthesis_match=True, synthesis_evidence=str(synth_hit),
                    attribute_required=True, attribute_match="MATCH", attribute_evidence=attr_evidence,
                    final_decision="ACCEPT", rejection_reason="ACCEPT — confirmed synthesis + contextual attribute"
                ))
            elif attr_match == "UNCERTAIN":
                return _with_flags(ContentValidationResult(
                    material_match=True, material_evidence=str(mat_hit),
                    target_identity_evidence=target_identity_evidence, precursor_evidence=prec_ev, transformation_evidence=trans_ev,
                    synthesis_match=True, synthesis_evidence=str(synth_hit),
                    attribute_required=True, attribute_match="UNCERTAIN", attribute_evidence=attr_evidence,
                    final_decision="UNCERTAIN", rejection_reason="UNCERTAIN — attributes found but not contextually linked"
                ))
            else:
                return _with_flags(ContentValidationResult(
                    material_match=True, material_evidence=str(mat_hit),
                    target_identity_evidence=target_identity_evidence, precursor_evidence=prec_ev, transformation_evidence=trans_ev,
                    synthesis_match=True, synthesis_evidence=str(synth_hit),
                    attribute_required=True, attribute_match="NO_MATCH", attribute_evidence="",
                    final_decision="REJECT", rejection_reason="REJECTED — required attributes not found"
                ))
        
        return _with_flags(ContentValidationResult(
            material_match=True, material_evidence=str(mat_hit),
            target_identity_evidence=target_identity_evidence, precursor_evidence=prec_ev, transformation_evidence=trans_ev,
            synthesis_match=True, synthesis_evidence=str(synth_hit),
            attribute_required=False, attribute_match="NOT_REQUIRED", attribute_evidence="",
            final_decision="ACCEPT", rejection_reason="ACCEPT — generic polymer synthesis title + deterministic content confirms target"
        ))

    # ─────────────────────────────────────────────────────────────────────────
    # Backward-compatible wrapper used by the orchestrator
    # ─────────────────────────────────────────────────────────────────────────

    def score_candidate(
        self, title: str, snippet: str, source_query: str
    ) -> Tuple[int, TitleScreeningStatus, dict]:
        """
        Backward-compatible wrapper. Treats GENERIC_VERIFY as MEDIUM (not yet ACCEPT).
        The orchestrator upgrades GENERIC_VERIFY → ACCEPT or REJECTED after content check.
        """
        score, tier, signals = self.score_candidate_tiered(title, snippet, source_query)
        if tier == TIER_ACCEPT:
            status = TitleScreeningStatus.STRONG if score > 70 else TitleScreeningStatus.MEDIUM
        elif tier == TIER_GENERIC_VERIFY:
            status = TitleScreeningStatus.MEDIUM
        else:
            status = TitleScreeningStatus.REJECT

        signals["intent_classification"] = tier
        signals["reason"] = signals.get("rejection_reason") or tier
        return score, status, signals


TitleScorer = CandidateScorer
