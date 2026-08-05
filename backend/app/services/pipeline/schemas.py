"""
app/services/pipeline/schemas.py

Pydantic schemas used for structured LLM extraction.
These strictly define the output format expected from Gemini.
"""
from pydantic import BaseModel, Field


class PatentExtraction(BaseModel):
    """
    Schema for extracting structured polymerization data from a single patent.
    All fields default to 'Not disclosed' per business rules to avoid hallucination.
    """
    url: str = Field(description="The source URL of the patent (populated automatically).", default="")
    patent_number: str = Field(description="The formal patent publication number (e.g., US1234567A)")
    patent_title: str = Field(description="Title of the patent")
    assignee: str = Field(description="The company or assignee who owns the patent")
    publication_year: str = Field(description="The year the patent was published")
    jurisdiction: str = Field(description="The country or jurisdiction of the patent (e.g., US, EP, WO)")

    polymerization_process: str = Field(
        description="The type of polymerization (e.g., emulsion, solution, bulk, suspension)"
    )

    acrylonitrile_content: str = Field(
        description="Target or final ACN content percentage (e.g., 33%)"
    )
    monomer_ratio: str = Field(
        description="Ratio of monomers used, such as Butadiene to Acrylonitrile"
    )
    water_amount: str = Field(
        description="Amount of water or aqueous medium used (usually parts per hundred monomer)"
    )
    emulsifier: str = Field(
        description="Type and amount of emulsifier/surfactant used (e.g., potassium oleate, sodium rosinate)"
    )
    initiator: str = Field(
        description="Type and amount of initiator/catalyst used (e.g., persulfates, redox systems)"
    )
    chain_transfer_agent: str = Field(
        description="Type and amount of chain transfer agent / modifier (e.g., t-dodecyl mercaptan, t-DDM)"
    )
    temperature: str = Field(
        description="Polymerization reaction temperature (e.g., 5-15°C for cold, 40-50°C for hot)"
    )
    reaction_time: str = Field(
        description="Duration of the polymerization reaction"
    )
    conversion: str = Field(
        description="Final monomer conversion percentage before shortstopping (e.g., 65-70%)"
    )
    coagulation: str = Field(
        description="Coagulation/flocculation process details (e.g., calcium chloride, acid coagulation)"
    )

    polymer_properties: str = Field(
        description="Key properties of the resulting polymer (e.g., Mooney viscosity, Tg, tensile strength)"
    )

    experimental_notes: str = Field(
        description="Any other important synthesis notes, specific equipment, or anomalous procedures"
    )


class AIStrategyResult(BaseModel):
    """
    Schema for the output of the AI Search Planning phase.
    """
    search_queries: list[str] = Field(
        description="A list of 3 to 5 optimized boolean search queries targeting polymer synthesis methods."
    )
    rationale: str = Field(
        description="Brief explanation of the search strategy."
    )


class ClassificationResult(BaseModel):
    """
    Schema for quickly classifying whether a downloaded patent should be kept.
    """
    is_relevant: bool = Field(
        description="True if the patent contains raw polymer synthesis/manufacturing details."
    )
    reason: str = Field(
        description="Brief reason for keeping or discarding the patent based on rejection rules."
    )
