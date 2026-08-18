import contextvars
from typing import Optional
from enum import Enum
import uuid

# Define valid stages as an Enum matching the user's requirements
class TelemetryStage(str, Enum):
    QUERY_EXPANSION = "QUERY_EXPANSION"
    PATENT_SEARCH = "PATENT_SEARCH"
    PATENT_EXTRACTION = "PATENT_EXTRACTION"
    PATENT_RANKING = "PATENT_RANKING"
    FAMILY_DEDUPLICATION = "FAMILY_DEDUPLICATION"
    VALIDATION = "VALIDATION"
    REPORT_GENERATION = "REPORT_GENERATION"
    RECIPE_GENERATION = "RECIPE_GENERATION"
    RECIPE_OPTIMIZATION = "RECIPE_OPTIMIZATION"
    OTHER = "OTHER"

# Context variables to hold state globally per async execution flow
current_run_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("current_run_id", default=None)
current_stage: contextvars.ContextVar[Optional[TelemetryStage]] = contextvars.ContextVar("current_stage", default=None)
current_project_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("current_project_id", default=None)
current_operation: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("current_operation", default=None)

def set_current_run_id(run_id: uuid.UUID | str | None):
    """Set the current research run ID in the async context."""
    if run_id:
        current_run_id.set(str(run_id))
    else:
        current_run_id.set(None)

def set_current_stage(stage: TelemetryStage | str | None):
    """Set the current stage in the async context."""
    if isinstance(stage, str):
        stage = TelemetryStage(stage)
    current_stage.set(stage)
    if stage:
        heartbeat(stage=stage.value if hasattr(stage, 'value') else str(stage))

def get_current_run_id() -> Optional[str]:
    return current_run_id.get()

def get_current_stage() -> Optional[TelemetryStage]:
    return current_stage.get()

def get_current_project_id() -> Optional[str]:
    return current_project_id.get()

def set_current_operation(operation: str | None):
    """Set the current operation in the async context."""
    current_operation.set(operation)

def get_current_operation() -> Optional[str]:
    return current_operation.get()

# Global heartbeat tracker (in-memory)
from datetime import datetime, timezone

# Dict mapping run_id (str) -> dict of { "last_heartbeat": datetime, "stage": str, "progress": str, "error": str }
ACTIVE_RUNS_HEARTBEAT: dict[str, dict] = {}

def heartbeat(run_id: str | None = None, stage: str | None = None, progress: str | None = None, error: str | None = None):
    rid = str(run_id) if run_id else get_current_run_id()
    if not rid:
        return
    
    if rid not in ACTIVE_RUNS_HEARTBEAT:
        ACTIVE_RUNS_HEARTBEAT[rid] = {
            "stage": None,
            "progress": None,
            "error": None
        }
        
    ACTIVE_RUNS_HEARTBEAT[rid]["last_heartbeat"] = datetime.now(timezone.utc)
    if stage is not None:
        ACTIVE_RUNS_HEARTBEAT[rid]["stage"] = stage
    if progress is not None:
        ACTIVE_RUNS_HEARTBEAT[rid]["progress"] = progress
    if error is not None:
        ACTIVE_RUNS_HEARTBEAT[rid]["error"] = error
