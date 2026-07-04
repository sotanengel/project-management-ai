"""PMDF Pydanticモデル群。

`KIND_TO_MODEL` は `kind` 文字列からモデルクラスへのマッピングであり、
E2-4のI/O層(`pmdf.io`)やE3のAPI層から共通で利用される公開インターフェース。
"""

from __future__ import annotations

from pmdf.models.approval import Approval
from pmdf.models.common import Attachment, PmdfBase, Provenance
from pmdf.models.decision import Decision, Option, RejectedReason
from pmdf.models.experiment import Experiment
from pmdf.models.initiative import Evm, Initiative, Schedule, WbsNode
from pmdf.models.metric import Metric, TimeSeriesPoint
from pmdf.models.objective import KeyResult, Objective
from pmdf.models.persona import Job, Persona
from pmdf.models.product import Product
from pmdf.models.release import Release
from pmdf.models.report import Report
from pmdf.models.risk import Risk
from pmdf.models.roadmap_item import RoadmapItem
from pmdf.models.stakeholder import ContactPolicy, Stakeholder
from pmdf.models.story import Priority, Story, StoryLinks

KIND_TO_MODEL: dict[str, type[PmdfBase]] = {
    "product": Product,
    "stakeholder": Stakeholder,
    "persona": Persona,
    "objective": Objective,
    "metric": Metric,
    "roadmap_item": RoadmapItem,
    "story": Story,
    "experiment": Experiment,
    "decision": Decision,
    "release": Release,
    "risk": Risk,
    "initiative": Initiative,
    "report": Report,
    "approval": Approval,
}

__all__ = [
    "KIND_TO_MODEL",
    "Approval",
    "Attachment",
    "ContactPolicy",
    "Decision",
    "Evm",
    "Experiment",
    "Initiative",
    "Job",
    "KeyResult",
    "Metric",
    "Objective",
    "Option",
    "Persona",
    "PmdfBase",
    "Priority",
    "Product",
    "Provenance",
    "RejectedReason",
    "Release",
    "Report",
    "Risk",
    "RoadmapItem",
    "Schedule",
    "Stakeholder",
    "Story",
    "StoryLinks",
    "TimeSeriesPoint",
    "WbsNode",
]
