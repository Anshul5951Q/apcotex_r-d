"""
app/models/__init__.py

Import all models here so Alembic's env.py registers them all with
Base.metadata by importing this single package.
"""
from app.models.user import User, UserRole
from app.models.research_run import ResearchRun, RunStatus
from app.models.report_metadata import ReportMetadata
from app.models.report_file import ReportFile, ReportFileType
from app.models.app_config import AppConfig
from app.models.patent_document import PatentDocument

__all__ = [
    "User",
    "UserRole",
    "ResearchRun",
    "RunStatus",
    "ReportMetadata",
    "ReportFile",
    "ReportFileType",
    "AppConfig",
    "PatentDocument",
]
