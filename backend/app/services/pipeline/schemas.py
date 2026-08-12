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
    FULL = "FULL"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"

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

class PolymerizationData(BaseModel):
    process: str = Field(description="The type of polymerization (e.g., emulsion, solution, bulk, suspension)", default="Not disclosed")
    monomers: str = Field(description="Monomers used in the reaction", default="Not disclosed")
    monomer_ratio: str = Field(description="Ratio of monomers used", default="Not disclosed")
    initiator: str = Field(description="Type and amount of initiator/catalyst used", default="Not disclosed")
    emulsifier: str = Field(description="Type and amount of emulsifier/surfactant used", default="Not disclosed")
    catalyst: str = Field(description="Type and amount of catalyst", default="Not disclosed")
    chain_transfer_agent: str = Field(description="Type and amount of chain transfer agent / modifier", default="Not disclosed")
    coagulation: str = Field(description="Coagulation/flocculation process details", default="Not disclosed")
    water_amount: str = Field(description="Amount of water or aqueous medium used", default="Not disclosed")

class ReactionConditions(BaseModel):
    temperature: str = Field(description="Polymerization reaction temperature", default="Not disclosed")
    time: str = Field(description="Duration of the polymerization reaction", default="Not disclosed")
    pressure: str = Field(description="Reaction pressure", default="Not disclosed")
    ph: str = Field(description="Reaction pH", default="Not disclosed")
    conversion: str = Field(description="Final monomer conversion percentage", default="Not disclosed")

class PropertiesData(BaseModel):
    solid_content: str = Field(description="Solid content percentage", default="Not disclosed")
    mooney_viscosity: str = Field(description="Mooney viscosity", default="Not disclosed")
    volatile_matter: str = Field(description="Volatile matter content", default="Not disclosed")
    ash: str = Field(description="Ash content", default="Not disclosed")
    other_properties: str = Field(description="Other key properties of the resulting polymer", default="Not disclosed")

class ExamplesData(BaseModel):
    example_tables: list[str] = Field(description="Extracted tables related to examples", default_factory=list)
    reaction_procedure: str = Field(description="The specific steps and procedure for the reaction", default="Not disclosed")
    experimental_notes: str = Field(description="Any other important synthesis notes or anomalies", default="Not disclosed")

class PatentExtraction(BaseModel):
    """
    Final Schema for extracting structured polymerization data from a single patent.
    """
    metadata: PatentMetadata = Field(default_factory=PatentMetadata)
    polymerization: PolymerizationData = Field(default_factory=PolymerizationData)
    reaction_conditions: ReactionConditions = Field(default_factory=ReactionConditions)
    properties: PropertiesData = Field(default_factory=PropertiesData)
    experimental_notes: ExamplesData = Field(default_factory=ExamplesData)
    claims: list[str] = Field(description="Independent claims of the patent", default_factory=list)
    parameters: list[ExtractedParameterSchema] = Field(default_factory=list)
    examples: list[PatentExample] = []

class ExtractionResult(BaseModel):
    status: ExtractionStatus
    patent_number: str
    extraction: PatentExtraction

class CompoundSearchProfile(BaseModel):
    """
    Schema for dynamic compound search profiles generated by the CompoundIntelligenceService.
    Replaces static/hardcoded compound rules.
    """
    original_input: str = Field(default="", description="The exact user-entered input string (preserved for traceability).")
    compound: str = Field(description="The user's raw input compound.")
    compound_name: str = Field(description="The normalized primary chemical name (e.g., 'Ethylene Propylene Diene Monomer').")
    synonyms: list[str] = Field(description="A broad list of synonyms and acronyms (e.g., ['EPDM', 'Ethylene-Propylene-Diene']).")
    abbreviations: list[str] = Field(description="Known abbreviations.")
    chemical_family: str = Field(description="The broad polymer family (e.g., 'EPDM', 'NBR', 'Fluoropolymer').")
    major_monomers: list[str] = Field(description="The individual monomers comprising this compound.")
    alternative_industry_names: list[str] = Field(description="Trade names or alternative industry names.")
    important_constraints: list[str] = Field(default_factory=list, description="Critical constraints from the original input that must be preserved (e.g., ['low acrylonitrile', 'high cis']).")
    research_intent: str = Field(default="", description="The research intent (e.g., 'polymerization', 'preparation', 'synthesis').")
    typical_polymerization_routes: list[str] = Field(description="Specific polymerization processes typically used (e.g., ['solution polymerization', 'Ziegler-Natta']).")
    typical_manufacturing_keywords: list[str] = Field(description="Common manufacturing terms (e.g., 'method for manufacturing', 'process for producing').")
    typical_cpc: list[str] = Field(description="Preferred CPC patent classes (e.g., ['C08F', 'C08L']).")
    typical_ipc: list[str] = Field(description="Preferred IPC patent classes.")
    related_chemistry: list[str] = Field(description="Chemicals or compounds often found alongside or related to the target.")
    competing_chemistry: list[str] = Field(description="Alternative compounds that indicate the patent is likely NOT about the target compound (e.g., if target is CR, competing might be NBR, SBR).")
    application_keywords: list[str] = Field(description="Negative signals indicating out-of-scope applications or downstream products (e.g., 'glove', 'tire', 'film', 'battery', 'adhesive').")
    manufacturing_keywords: list[str] = Field(description="Words highly indicative of raw synthesis (e.g., 'initiator', 'emulsifier', 'reactor', 'conversion', 'catalyst').")
    target_composition_keywords: list[str] = Field(default_factory=list, description="Keywords indicating target composition or property (e.g., ['acrylonitrile', 'ACN']).")
    target_composition_range: str = Field(default="", description="The target numerical range for the composition (e.g., '18-24%').")
    search_queries: list[SearchQuery] = Field(default_factory=list, description="Dynamically generated search queries.")

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

class ReportPatentDetails(BaseModel):
    patent_number: str = Field(description="The formal patent publication number (e.g., US1234567A)")
    patent_title: str = Field(description="Title of the patent")
    assignee: str | None = Field(default=None, description="The company or assignee who owns the patent")
    jurisdiction: str | None = Field(default=None, description="The country or jurisdiction of the patent (e.g., US, EP, WO)")
    publication_year: str | None = Field(default=None, description="The year the patent was published")
    polymer_type: str | None = Field(default=None, description="The type of polymer synthesized")
    relevance_to_target: str = Field(default="Not disclosed", description="Why this patent is relevant to the target compound")

class ReportPatentMethodology(BaseModel):
    polymerization_process: str | None = Field(default=None, description="Polymerization process (e.g., emulsion polymerization)")
    monomer_system: str | None = Field(default=None, description="Monomer system used")
    monomer_ratio: str | None = Field(default=None, description="Exact monomer ratio or contents")
    water_amount: str | None = Field(default=None, description="Water amount")
    emulsifier: str | None = Field(default=None, description="Emulsifier used")
    emulsifier_loading: str | None = Field(default=None, description="Emulsifier loading")
    initiator: str | None = Field(default=None, description="Initiator used")
    initiator_loading: str | None = Field(default=None, description="Initiator loading")
    catalyst_activator: str | None = Field(default=None, description="Catalyst / activator used")
    chain_transfer_agent: str | None = Field(default=None, description="Chain-transfer agent used")
    chain_transfer_dosage: str | None = Field(default=None, description="Chain-transfer dosage")
    polymerization_temperature: str | None = Field(default=None, description="Polymerization temperature")
    pressure: str | None = Field(default=None, description="Pressure")
    ph: str | None = Field(default=None, description="pH")
    reaction_time: str | None = Field(default=None, description="Reaction time")
    conversion: str | None = Field(default=None, description="Conversion")
    coagulation_conditions: str | None = Field(default=None, description="Coagulation conditions")
    post_treatment: str | None = Field(default=None, description="Post-treatment")
    raw_polymer_properties: str | None = Field(default=None, description="Raw polymer properties")

class ReportPatent(BaseModel):
    patent_details: ReportPatentDetails
    polymerization_method: ReportPatentMethodology
    experimental_evidence: list[str] = Field(description="List of logical bullet points synthesizing the examples")
    technical_relevance: str = Field(description="Explanation of WHY the patent is relevant to the requested polymerization research")

class PatentResearchReport(BaseModel):
    title: str | None = Field(default=None, description="Title of the report")
    abstract: str | None = Field(default=None, description="Abstract of the report")
    methodology_patents: list[ReportPatent] = Field(description="List of extracted patents and their methodologies", default_factory=list)
    cross_patent_comparison: list[str] = Field(description="Cross-patent comparison and synthesis trends (concise bullet points)", default_factory=list)
    references: list[str] = Field(description="List of references (only the selected patents with URLs)", default_factory=list)

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
