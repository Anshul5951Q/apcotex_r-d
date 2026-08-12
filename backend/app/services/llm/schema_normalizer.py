from typing import Any, Dict
import copy
import importlib
import logging

logger = logging.getLogger(__name__)

def normalize_gemini_schema(schema: Dict[str, Any]) -> Dict[str, Any]:
    """
    Recursively resolves all $ref references in a Pydantic JSON schema by inlining
    definitions from $defs and removes $defs. This produces a flattened schema
    compatible with Gemini's structured output requirements.
    
    Also includes a fallback for missing refs via dynamic import.
    
    Additionally, removes nested 'required' arrays as Gemini may have issues with them.
    """
    schema_copy = copy.deepcopy(schema)
    defs = schema_copy.pop("$defs", {})
    
    def resolve(node: Any) -> Any:
        if isinstance(node, dict):
            if "$ref" in node:
                ref_key = node["$ref"].split("/")[-1]
                if ref_key in defs:
                    resolved = resolve(copy.deepcopy(defs[ref_key]))
                    return resolved
                else:
                    # Fallback: try to dynamically import the class
                    try:
                        module_path, class_name = ref_key.split("__", 1)
                        module = importlib.import_module(f"app.{module_path}")
                        cls = getattr(module, class_name)
                        cls_schema = cls.model_json_schema()
                        if "$defs" in cls_schema:
                            defs.update(cls_schema.pop("$defs"))
                        resolved = resolve(cls_schema)
                        return resolved
                    except Exception as e:
                        logger.warning(f"Could not resolve $ref {ref_key}: {e}")
                        return {}
            
            # Special case for anyOf handling if Pydantic uses it for Optionals/Nullables
            if "anyOf" in node:
                # Gemini doesn't fully support anyOf in all SDK versions, but we can try to flatten 
                # if it's just [type, null]
                non_nulls = [t for t in node["anyOf"] if t.get("type") != "null"]
                if len(non_nulls) == 1:
                    # Replace anyOf with the non-null type, keeping it nullable if needed
                    resolved_type = resolve(non_nulls[0])
                    # If nullable is supported by Gemini we can set it, otherwise we just use the type
                    # For now, just use the resolved inner type
                    resolved_node = {k: v for k, v in node.items() if k != "anyOf"}
                    resolved_node.update(resolved_type)
                    return resolved_node
            
            # Recursively resolve all dictionary values
            for k, v in node.items():
                node[k] = resolve(v)
            return node
            
        elif isinstance(node, list):
            return [resolve(item) for item in node]
        else:
            return node

    resolved_schema = resolve(schema_copy)
    
    # Remove 'required' arrays - Gemini has issues with them
    # BUT preserve required fields for RankedCandidate to ensure decision/reason are always output
    def remove_required_selective(node: Any, path: str = "") -> Any:
        if isinstance(node, dict):
            # Check if this is RankedCandidate - preserve its required fields
            if "required" in node:
                # Check if this node has the RankedCandidate structure (has decision/reason fields)
                properties = node.get("properties", {})
                has_decision = "decision" in properties
                has_reason = "reason" in properties
                
                # Preserve required fields for RankedCandidate-like objects
                if has_decision and has_reason:
                    logger.info(f"Preserving required fields for {path}: {node['required']}")
                else:
                    del node["required"]
            for key, value in list(node.items()):
                new_path = f"{path}.{key}" if path else key
                node[key] = remove_required_selective(value, new_path)
        elif isinstance(node, list):
            for idx, item in enumerate(node):
                node[idx] = remove_required_selective(item, path)
        return node
    
    logger.info("Removing required fields from schema (except RankedCandidate)...")
    resolved_schema = remove_required_selective(resolved_schema)
    logger.info("Done. Required fields removed (RankedCandidate preserved).")
    
    return resolved_schema
