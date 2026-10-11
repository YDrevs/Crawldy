from app.enrich.contracts import TaskType
from app.enrich.tasks.base import TaskSpec, build_request
from app.enrich.tasks.remediation import REMEDIATION_PLAN
from app.enrich.tasks.root_cause import ROOT_CAUSE_GROUPING
from app.enrich.tasks.site_understanding import SITE_UNDERSTANDING

TASKS: dict[TaskType, TaskSpec] = {
    spec.type: spec
    for spec in (SITE_UNDERSTANDING, ROOT_CAUSE_GROUPING, REMEDIATION_PLAN)
}

__all__ = [
    "REMEDIATION_PLAN",
    "ROOT_CAUSE_GROUPING",
    "SITE_UNDERSTANDING",
    "TASKS",
    "TaskSpec",
    "build_request",
]
