"""
Regression test for Gemini schema validation.
Tests that all schemas used in the pipeline can be normalized and validated.
"""
import pytest
from app.services.pipeline.schemas import (
    PatentResearchReport,
    PatentExtraction,
    BatchAnalysisResult,
    PatentRankResult,
    RankedCandidateList,
    ContentValidationSchema,
)
from app.services.llm.schema_normalizer import normalize_gemini_schema


def validate_gemini_schema(schema: dict, path: str = "root") -> list[str]:
    """
    Recursively validate that all required fields exist in properties.
    Returns list of validation errors.
    """
    errors = []
    
    if not isinstance(schema, dict):
        return errors
        
    if "properties" in schema:
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        
        for req_field in required:
            if req_field not in properties:
                errors.append(f"Path: {path} | Required field '{req_field}' not found in properties")
        
        for prop_name, prop_schema in properties.items():
            nested_path = f"{path}.{prop_name}"
            if isinstance(prop_schema, dict):
                if "items" in prop_schema and isinstance(prop_schema["items"], dict):
                    errors.extend(validate_gemini_schema(prop_schema["items"], f"{nested_path}.items"))
                else:
                    errors.extend(validate_gemini_schema(prop_schema, nested_path))
            elif isinstance(prop_schema, list):
                for idx, item in enumerate(prop_schema):
                    if isinstance(item, dict):
                        errors.extend(validate_gemini_schema(item, f"{nested_path}[{idx}]"))
    
    return errors


def check_for_refs(node, path="root"):
    """Check for unresolved $ref and $defs"""
    refs = []
    if isinstance(node, dict):
        if "$ref" in node:
            refs.append(f"Unresolved $ref at {path}: {node['$ref']}")
        if "$defs" in node:
            refs.append(f"Unresolved $defs at {path}: {list(node['$defs'].keys())}")
        for k, v in node.items():
            refs.extend(check_for_refs(v, f"{path}.{k}"))
    elif isinstance(node, list):
        for idx, item in enumerate(node):
            refs.extend(check_for_refs(item, f"{path}[{idx}]"))
    return refs


@pytest.mark.parametrize("schema_class,schema_name", [
    (PatentResearchReport, "PatentResearchReport"),
    (PatentExtraction, "PatentExtraction"),
    (BatchAnalysisResult, "BatchAnalysisResult"),
    (PatentRankResult, "PatentRankResult"),
    (RankedCandidateList, "RankedCandidateList"),
    (ContentValidationSchema, "ContentValidationSchema"),
])
def test_schema_normalization_and_validation(schema_class, schema_name):
    """Test that schemas can be normalized and pass validation."""
    raw_schema = schema_class.model_json_schema()
    normalized_schema = normalize_gemini_schema(raw_schema)
    
    # Check for unresolved refs
    refs = check_for_refs(normalized_schema)
    assert len(refs) == 0, f"Found unresolved refs in {schema_name}: {refs}"
    
    # Validate required fields
    validation_errors = validate_gemini_schema(normalized_schema)
    assert len(validation_errors) == 0, f"Schema validation failed for {schema_name}: {validation_errors}"


def test_patent_research_report_no_required_fields():
    """Test that PatentResearchReport has no required fields after normalization."""
    raw_schema = PatentResearchReport.model_json_schema()
    normalized_schema = normalize_gemini_schema(raw_schema)
    
    # After normalization, all required fields should be removed
    # to avoid Gemini validation issues
    def has_required(node):
        if isinstance(node, dict):
            if "required" in node:
                return True
            for v in node.values():
                if has_required(v):
                    return True
        elif isinstance(node, list):
            for item in node:
                if has_required(item):
                    return True
        return False
    
    assert not has_required(normalized_schema), "PatentResearchReport should have no required fields after normalization"
