"""
app/services/pipeline/schemas.py

Pydantic schemas used for structured LLM extraction.
These strictly define the output format expected from Gemini.
"""
from typing import Dict, List, Optional
from enum import Enum
from pydantic import BaseModel, Field

class CandidateState(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    REVIEW = "REVIEW"
    REJECTED = "REJECTED"

class RelevanceClass(str, Enum):
    DIRECT = "DIRECT"
    INDIRECT = "INDIRECT"
    IRRELEVANT = "IRRELEVANT"

class MetadataQualification(str, Enum):
    KEEP = "KEEP"
    REVIEW = "REVIEW"
    REJECT = "REJECT"

class ExtractionStatus(str, Enum):
    FULL = "FULL"                          # Both deterministic + LLM succeeded
    PARTIAL = "PARTIAL"                    # Only deterministic; LLM skipped or found nothing extra
    FAILED = "FAILED"                      # Complete failure (fetch/parse error)
    LLM_FAILED = "LLM_FAILED"             # LLM was attempted but failed; deterministic preserved
    NO_USABLE_EVIDENCE = "NO_USABLE_EVIDENCE"  # Neither deterministic nor LLM found any parameters

from enum import Enum

class SearchField(str, Enum):
    TITLE = "TITLE"
    TAC = "TAC"

class SearchCategory(str, Enum):
    MANUFACTURING = "MANUFACTURING"
    PREPARATION = "PREPARATION"
    POLYMERIZATION = "POLYMERIZATION"
    PROCESS = "PROCESS"
    CHEMISTRY = "CHEMISTRY"
    EXACT = "EXACT"
    CONSTRAINT = "CONSTRAINT"
    SYNTHESIS = "SYNTHESIS"
    SYNONYM = "SYNONYM"
    BROAD = "BROAD"

class SearchPriority(str, Enum):
    PRIMARY = "PRIMARY"
    SECONDARY = "SECONDARY"
    FALLBACK = "FALLBACK"

class TargetAttribute(BaseModel):
    name: str
    condition: str
    terms: list[str]

class SearchQuery(BaseModel):
    query: str
    field: SearchField = SearchField.TITLE
    category: SearchCategory = SearchCategory.POLYMERIZATION
    priority: SearchPriority = SearchPriority.PRIMARY

class RankedCandidate(BaseModel):
    publication_number: str = Field(description="Must perfectly match input publication number")
    score: int = Field(description="Relevance score from 0-100")
    decision: str = Field(description="Decision: 'KEEP' or 'REJECT'")
    reason: str = Field(description="Brief justification for the decision")
    title_evidence: list[str] = Field(default_factory=list, description="Key phrases from the title supporting the decision")

class RankedCandidateList(BaseModel):
    ranked_candidates: list[RankedCandidate]

class ConfidenceDimensions(BaseModel):
    compound_evidence: list[str] = Field(default_factory=list)
    matched_monomers: list[str] = Field(default_factory=list)
    matched_synonyms: list[str] = Field(default_factory=list)
    matched_chemistry_family: list[str] = Field(default_factory=list)
    manufacturing_evidence: list[str] = Field(default_factory=list)
    recipe_evidence: list[str] = Field(default_factory=list)
    negative_evidence: list[str] = Field(default_factory=list)
    competing_chemistry: list[str] = Field(default_factory=list)
    search_confidence: int = 0
    target_chemistry_score: int = 0
    synthesis_score: int = 0
    recipe_score: int = 0
    
    @property
    def has_compound_evidence(self) -> bool:
        return len(self.compound_evidence) > 0 or len(self.matched_monomers) >= 2 or len(self.matched_synonyms) > 0 or len(self.matched_chemistry_family) > 0
        
    @property
    def has_manufacturing_evidence(self) -> bool:
        return len(self.manufacturing_evidence) > 0
        
    @property
    def has_recipe_evidence(self) -> bool:
        return len(self.recipe_evidence) > 0

    @property
    def overall_confidence(self) -> int:
        score = 0
        score += len(self.compound_evidence) * 50
        score += len(self.matched_synonyms) * 30
        score += len(self.matched_monomers) * 15
        score += len(self.matched_chemistry_family) * 10
        score += len(self.manufacturing_evidence) * 10
        score += len(self.recipe_evidence) * 15
        score += self.search_confidence
        score -= len(self.negative_evidence) * 20
        score -= len(self.competing_chemistry) * 15
        return max(0, score)

class EvidenceLedger(BaseModel):
    state: CandidateState = CandidateState.LOW
    relevance: RelevanceClass = RelevanceClass.INDIRECT
    dimensions: ConfidenceDimensions = Field(default_factory=ConfidenceDimensions)
    matched_queries: list[str] = Field(default_factory=list)
    query_match_count: int = 0
    search_families: list[SearchCategory] = Field(default_factory=list)
    history: list[str] = Field(default_factory=list)
    rejection_reason: str = ""
    
    def log(self, message: str):
        self.history.append(message)

class StructuralEvidence(BaseModel):
    has_preparation_example: bool = False
    has_experimental_example: bool = False
    has_working_example: bool = False
    has_embodiment: bool = False
    has_detailed_description: bool = False
    has_claims: bool = False
    example_count: int = 0
    table_count: int = 0
    temperature_count: int = 0
    pressure_count: int = 0
    initiator_count: int = 0
    emulsifier_count: int = 0
    chain_transfer_count: int = 0
    conversion_count: int = 0
    coagulation_count: int = 0
    wt_percent_count: int = 0
    phr_count: int = 0
    numeric_density: float = 0.0
    example_density: float = 0.0

class ExtractedParameterSchema(BaseModel):
    name: str = ""
    category: str = ""
    value: str = ""
    unit: str = ""
    context: str = ""
    section: str = ""
    example_number: str = ""
    source_sentence: str = ""
    confidence: float = 0.0
    source_offset: int = 0
    extraction_method: str = "deterministic"

class PatentExample(BaseModel):
    number: str = ""
    type: str = ""
    title: str = ""
    raw_text: str = ""
    extracted_parameters: list[ExtractedParameterSchema] = []

class ParsedPatent(BaseModel):
    """
    Schema for the deterministic output of the parser stage.
    """
    url: str = ""
    patent_number: str = Field(description="Canonical patent identifier", default="")
    title: str = Field(description="Title of the patent", default="")
    jurisdiction: str = Field(description="Jurisdiction of the patent", default="")
    publication_date: str = Field(description="Publication date of the patent", default="")
    assignee: str = Field(description="Assignee of the patent", default="")
    metadata: Dict[str, str] = Field(default_factory=dict)
    abstract: str = ""
    summary: str = ""
    detailed_description: str = ""
    examples: str = ""
    tables: List[Dict] = Field(default_factory=list)
    claims: str = ""
    structural_evidence: StructuralEvidence = Field(default_factory=StructuralEvidence)
    
    def get_llm_context(self) -> str:
        """Returns only the relevant sections for the LLM to process."""
        context = []
        if self.abstract:
            context.append(f"--- ABSTRACT ---\n{self.abstract}")
        if self.summary:
            context.append(f"--- SUMMARY ---\n{self.summary}")
        if self.detailed_description:
            # We want to include detailed description but it can be huge, we'll slice it in extractor_service
            context.append(f"--- DETAILED DESCRIPTION ---\n{self.detailed_description}")
        if self.examples:
            context.append(f"--- EXAMPLES ---\n{self.examples}")
        if self.tables:
            context.append(f"--- TABLES ---\n{self.tables}")
        return "\n\n".join(context)

class ContentValidationSchema(BaseModel):
    relevance: RelevanceClass
    confidence: int
    target_chemistry_evidence: list[str] = Field(default_factory=list)
    synthesis_evidence: list[str] = Field(default_factory=list)
    exclusion_reason: str = ""
class PatentMetadata(BaseModel):
    url: str = Field(description="The source URL of the patent (populated automatically).", default="")
    patent_number: str = Field(description="The formal patent publication number (e.g., US1234567A)", default="Not disclosed")
    patent_title: str = Field(description="Title of the patent", default="Not disclosed")
    assignee: str = Field(description="The company or assignee who owns the patent", default="Not disclosed")
    publication_year: str = Field(description="The year the patent was published", default="Not disclosed")
    jurisdiction: str = Field(description="The country or jurisdiction of the patent (e.g., US, EP, WO)", default="Not disclosed")
    legal_status: str = Field(description="The legal status of the patent (e.g. Active, Expired)", default="Unknown")
    quality: str = Field(description="The validation quality of the extraction (High, Medium, Low)", default="Not disclosed")
    extraction_score: int = Field(description="The relative score for candidate sorting", default=0)

class ExamplesData(BaseModel):
    example_tables: list[str] = Field(description="Extracted tables related to examples", default_factory=list)
    reaction_procedure: str = Field(description="The specific steps and procedure for the reaction", default="Not disclosed")
    experimental_notes: str = Field(description="Any other important synthesis notes or anomalies", default="Not disclosed")

class PatentExtraction(BaseModel):
    """
    Final Schema for extracting structured polymerization data from a single patent.
    """
    metadata: PatentMetadata = Field(default_factory=PatentMetadata)
    experimental_notes: ExamplesData = Field(default_factory=ExamplesData)
    claims: list[str] = Field(description="Independent claims of the patent", default_factory=list)
    parameters: list[ExtractedParameterSchema] = Field(default_factory=list)
    examples: list[PatentExample] = []

class ExtractionResult(BaseModel):
    status: ExtractionStatus
    patent_number: str
    extraction: PatentExtraction

class LLMCompoundSearchProfile(BaseModel):
    """
    Compact, LLM-facing schema for generating query expansion profiles.
    Used exclusively to minimize token usage.
    """
    compound_name: str = Field(description="The normalized primary chemical name (e.g., 'Ethylene Propylene Diene Monomer').")
    base_chemistry: str = Field(description="The core base chemistry for the target material, excluding constraints.")
    target_attributes: list[TargetAttribute] = Field(default_factory=list, description="Specific target attributes identified from the input.")
    synonyms: list[str] = Field(description="A broad list of synonyms and acronyms (e.g., ['EPDM', 'Ethylene-Propylene-Diene']).")
    material_aliases: list[str] = Field(default_factory=list, description="Broader list of aliases, abbreviations, and exact names for the material.")
    precursor_terms: list[str] = Field(default_factory=list, description="Raw materials, monomers, or precursor polymers used to create the target material (e.g., ['NBR', 'nitrile rubber'] for HNBR).")
    transformation_terms: list[str] = Field(default_factory=list, description="Processes used to transform the precursor into the target material (e.g., ['hydrogenation', 'crosslinking']).")
    manufacturing_intent: str = Field(default="", description="The research intent (e.g., 'polymerization', 'preparation', 'synthesis').")
    synthesis_terms: list[str] = Field(default_factory=list, description="Dynamic synthesis or manufacturing terms derived from the input (e.g., ['polymerization', 'copolymerization', 'preparation']).")
    downstream_application_terms: list[str] = Field(default_factory=list, description="Terms indicating downstream application or compounding rather than synthesis (e.g., ['article', 'glove', 'vulcanization', 'compound']).")
    relevant_parameter_categories: list[str] = Field(default_factory=list, description="Specific technical parameter categories highly relevant to this chemistry (e.g., ['catalyst', 'temperature', 'monomer ratio', 'conversion']).")
    derivative_exclusion_terms: list[str] = Field(default_factory=list, description="Specific chemical derivatives or modifications that should be EXCLUDED unless explicitly requested (e.g. ['HNBR', 'hydrogenated NBR', 'carboxylated NBR'] for a pure NBR query).")
    search_queries: list[str] = Field(default_factory=list, description="Dynamically generated search query strings.")

class CompoundSearchProfile(BaseModel):
    """
    Internal pipeline schema containing deterministic sets derived from the LLM output.
    This schema is NEVER sent back to the LLM as a JSON schema.
    """
    original_input: str = ""
    compound: str = ""
    compound_name: str = ""
    base_chemistry: str = ""
    synonyms: list[str] = Field(default_factory=list)
    abbreviations: list[str] = Field(default_factory=list)
    material_aliases: list[str] = Field(default_factory=list)
    precursor_terms: list[str] = Field(default_factory=list)
    transformation_terms: list[str] = Field(default_factory=list)
    chemical_family: str = ""
    major_monomers: list[str] = Field(default_factory=list)
    alternative_industry_names: list[str] = Field(default_factory=list)
    important_constraints: list[str] = Field(default_factory=list)
    target_attributes: list[TargetAttribute] = Field(default_factory=list)
    research_intent: str = ""
    synthesis_terms: list[str] = Field(default_factory=list)
    downstream_application_terms: list[str] = Field(default_factory=list)
    typical_polymerization_routes: list[str] = Field(default_factory=list)
    typical_manufacturing_keywords: list[str] = Field(default_factory=list)
    typical_cpc: list[str] = Field(default_factory=list)
    typical_ipc: list[str] = Field(default_factory=list)
    related_chemistry: list[str] = Field(default_factory=list)
    competing_chemistry: list[str] = Field(default_factory=list)
    application_keywords: list[str] = Field(default_factory=list)
    manufacturing_keywords: list[str] = Field(default_factory=list)
    target_composition_keywords: list[str] = Field(default_factory=list)
    target_composition_range: str = ""
    relevant_parameter_categories: list[str] = Field(default_factory=list)
    derivative_exclusion_terms: list[str] = Field(default_factory=list)
    search_queries: list[SearchQuery] = Field(default_factory=list)

class ReportExampleEvidence(BaseModel):
    example_id: str
    relevance_classification: str = Field(default="UNKNOWN", description="POLYMERIZATION_RELEVANT, POLYMER_CHARACTERIZATION_RELEVANT, COMPOUNDING_ONLY, IRRELEVANT")
    extracted_parameters: list[ExtractedParameterSchema] = Field(default_factory=list)
    
class ReportPatentEvidence(BaseModel):
    patent_number: str
    title: str
    jurisdiction: str
    assignee: str
    publication_year: str
    url: str
    discovery_source: str = Field(default="NORMAL", description="NORMAL, COMPETITOR, or WEBSITE")
    competitor_name: str | None = Field(default=None, description="Competitor name if discovery_source is COMPETITOR")
    overall_patent_parameters: list[ExtractedParameterSchema] = Field(default_factory=list)
    examples: list[ReportExampleEvidence] = Field(default_factory=list)
    technical_findings: list[str] = Field(default_factory=list)
    limitations_or_missing_data: list[str] = Field(default_factory=list)
    # Source text: abstract + deterministically-extracted relevant passages.
    # Used as the primary evidence carrier when structured parameter extraction yields 0 params.
    source_text: str = Field(default="", description="Relevant source passages (abstract, synthesis sections, examples text)")
    relevance_tier: str = Field(default="", description="Relevance tier from title screening: STRONG, MEDIUM, or WEAK")
    relevance_score: float = Field(default=0.0, description="Numeric relevance score from title screening")


class ReportPatentDetails(BaseModel):
    patent_number: str = Field(description="The formal patent publication number (e.g., US1234567A)")
    patent_title: str = Field(description="Title of the patent")
    assignee: str | None = Field(default=None, description="The company or assignee who owns the patent")
    jurisdiction: str | None = Field(default=None, description="The country or jurisdiction of the patent (e.g., US, EP, WO)")
    publication_year: str | None = Field(default=None, description="The year the patent was published")
    priority_date: str | None = Field(default=None, description="The priority date of the patent, if available")
    legal_status: str | None = Field(default=None, description="The legal status (Active, Expired, etc.)")
    polymer_type: str | None = Field(default=None, description="The type of polymer synthesized")
    relevance_to_target: str = Field(default="Not disclosed", description="Why this patent is relevant to the target compound")
    relevance_tier: str = Field(default="PRIMARY", description="Classification tier: PRIMARY or SECONDARY")

class ReportPatentMethodology(BaseModel):
    dynamic_parameters: list[str] = Field(description="Dynamically extracted reaction parameters formatted as 'Key: Value'")

class ReportPatent(BaseModel):
    patent_details: ReportPatentDetails
    polymerization_method: ReportPatentMethodology
    experimental_evidence: list[str] = Field(description="List of logical bullet points synthesizing the examples")
    technical_relevance: str = Field(description="Explanation of WHY the patent is relevant to the requested polymerization research")

class PatentResearchReport(BaseModel):
    title: str | None = Field(default=None, description="Title of the report")
    abstract: str | None = Field(default=None, description="Abstract of the report")
    methodology_patents: list[ReportPatent] = Field(description="List of extracted patents (PRIMARY tier)", default_factory=list)
    cross_patent_comparison: list[str] = Field(description="Cross-patent comparison and synthesis trends (only when >= 2 PRIMARY patents)", default_factory=list)
    conclusion: str | None = Field(default=None, description="Conclusion of the report")
    references: list[str] = Field(description="References from validated evidence only", default_factory=list)

class LLMPatentResearchReport(BaseModel):
    """
    Schema for the LLM to output the abstract, cross-comparison, and conclusion.
    The methodology_patents array is deterministically injected by the orchestrator.
    """
    title: str | None = Field(default=None, description="Title of the report")
    abstract: str | None = Field(default=None, description="Abstract of the report")
    cross_patent_comparison: list[str] = Field(description="Cross-patent comparison and synthesis trends (only when >= 2 PRIMARY patents)", default_factory=list)
    conclusion: str | None = Field(default=None, description="Conclusion of the report")
    references: list[str] = Field(description="References from validated evidence only", default_factory=list)

class PatentBatchFindings(BaseModel):
    patent_number: str
    findings: str

class BatchAnalysisResult(BaseModel):
    patent_findings: list[PatentBatchFindings] = Field(default_factory=list)

class PatentRank(BaseModel):
    """
    Schema for an individual patent ranking.
    """
    patent: str = Field(description="The patent number (e.g., US6753382).")
    score: int = Field(description="The relevance score from 0 to 100.")
    reason: str = Field(description="Brief reason for the score, specifically relating to synthesis/polymerization detail.")

class PatentRankList(BaseModel):
    """
    Schema for a list of ranked patents.
    """
    rankings: list[PatentRank] = Field(description="A sorted list of ranked patents.")

class RankingStatus(str, Enum):
    SUCCESS = "SUCCESS"
    EMPTY = "EMPTY"
    PARTIAL = "PARTIAL"
    PROVIDER_ERROR = "PROVIDER_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"

class PatentRankResult(BaseModel):
    """
    Wrapper for the ranking result to cleanly differentiate business logic from infrastructure failures.
    """
    status: RankingStatus
    rankings: list[PatentRank] = Field(default_factory=list)
    provider: str
    error: Optional[str] = None
