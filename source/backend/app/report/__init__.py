"""Шар звітів: AuditOutcome → ReportDocument → JSON / docx."""

from app.report.builder import build_evidence, build_report
from app.report.source import source_from_outcome
from app.report.types import ReportDocument, ReportSource

__all__ = [
    "ReportDocument",
    "ReportSource",
    "build_evidence",
    "build_report",
    "source_from_outcome",
]
