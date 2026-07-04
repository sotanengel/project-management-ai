"""E2-4: hypothesisによるPMDFエンティティのプロパティベーステスト用戦略。

各`kind`について、対応するPydanticモデルのインスタンスをランダム生成する
`hypothesis.strategies.SearchStrategy`を提供する。生成される値は各モデルの
フィールド制約(正規表現パターン・enum等)を満たすように構築している。
"""

from __future__ import annotations

from datetime import UTC, datetime

from hypothesis import strategies as st
from pmdf.models import (
    Approval,
    ContactPolicy,
    Decision,
    Evm,
    Experiment,
    Initiative,
    Job,
    KeyResult,
    Metric,
    Objective,
    Option,
    Persona,
    Priority,
    Product,
    Provenance,
    RejectedReason,
    Release,
    Report,
    Risk,
    RoadmapItem,
    Schedule,
    Stakeholder,
    Story,
    StoryLinks,
    TimeSeriesPoint,
    WbsNode,
)

# YAML/JSON往復で問題を起こしにくい安全な文字集合(制御文字・サロゲートを除外)。
_SAFE_TEXT_ALPHABET = st.characters(
    blacklist_categories=("Cs", "Cc"),
    blacklist_characters="﻿",
)


def _safe_text(min_size: int = 1, max_size: int = 20) -> st.SearchStrategy[str]:
    return st.text(alphabet=_SAFE_TEXT_ALPHABET, min_size=min_size, max_size=max_size)


def _ulid_suffix() -> st.SearchStrategy[str]:
    alphabet = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
    return st.text(alphabet=alphabet, min_size=26, max_size=26)


def _id_strategy(prefix: str) -> st.SearchStrategy[str]:
    return _ulid_suffix().map(lambda suffix: f"{prefix}-{suffix}")


def _pmdf_version_strategy() -> st.SearchStrategy[str]:
    part = st.integers(min_value=0, max_value=99)
    return st.tuples(part, part, part).map(lambda p: f"{p[0]}.{p[1]}.{p[2]}")


def _created_by_strategy() -> st.SearchStrategy[str]:
    name = st.text(alphabet=st.characters(whitelist_categories=("L", "N")), min_size=1, max_size=10)
    user = name.map(lambda n: f"user:{n}")
    agent = st.tuples(name, name).map(lambda p: f"agent:{p[0]}@v{p[1]}")
    return st.one_of(user, agent)


def _datetime_strategy() -> st.SearchStrategy[datetime]:
    return st.datetimes(
        min_value=datetime(2020, 1, 1),
        max_value=datetime(2030, 1, 1),
        timezones=st.just(UTC),
    )


def _provenance_strategy() -> st.SearchStrategy[Provenance]:
    return st.builds(
        Provenance,
        created_by=_created_by_strategy(),
        approved_by=st.none() | _safe_text(),
        updated_at=_datetime_strategy(),
    )


def _product_strategy() -> st.SearchStrategy[Product]:
    return st.builds(
        Product,
        pmdf_version=_pmdf_version_strategy(),
        kind=st.just("product"),
        id=_id_strategy("prod"),
        provenance=_provenance_strategy(),
        attachments=st.just([]),
        name=_safe_text(),
        vision=_safe_text(),
        target=st.none() | _safe_text(),
        positioning=st.none() | _safe_text(),
        lifecycle_stage=st.sampled_from(["introduction", "growth", "maturity", "decline"]),
        north_star_metric=st.none() | _id_strategy("metric"),
    )


def _stakeholder_strategy() -> st.SearchStrategy[Stakeholder]:
    contact_policy = st.builds(
        ContactPolicy,
        personal_name=st.none() | _safe_text(),
        channel=st.none() | _safe_text(),
        frequency=st.none() | _safe_text(),
    )
    return st.builds(
        Stakeholder,
        pmdf_version=_pmdf_version_strategy(),
        kind=st.just("stakeholder"),
        id=_id_strategy("stakeholder"),
        provenance=_provenance_strategy(),
        attachments=st.just([]),
        name=_safe_text(),
        role=_safe_text(),
        organization=st.none() | _safe_text(),
        interests=st.lists(_safe_text(), max_size=3),
        influence=st.sampled_from(["low", "medium", "high", "critical"]),
        contact_policy=st.none() | contact_policy,
    )


def _persona_strategy() -> st.SearchStrategy[Persona]:
    job = st.builds(Job, situation=_safe_text(), motivation=_safe_text(), outcome=_safe_text())
    return st.builds(
        Persona,
        pmdf_version=_pmdf_version_strategy(),
        kind=st.just("persona"),
        id=_id_strategy("persona"),
        provenance=_provenance_strategy(),
        attachments=st.just([]),
        name=_safe_text(),
        attributes=st.dictionaries(_safe_text(max_size=8), _safe_text(max_size=8), max_size=3),
        pain_points=st.lists(_safe_text(), max_size=3),
        jobs=st.lists(job, min_size=1, max_size=3),
    )


def _objective_strategy() -> st.SearchStrategy[Objective]:
    key_result = st.builds(
        KeyResult,
        description=_safe_text(),
        target_value=st.floats(allow_nan=False, allow_infinity=False, width=32),
        current_value=st.none() | st.floats(allow_nan=False, allow_infinity=False, width=32),
    )
    period = st.tuples(
        st.integers(min_value=2020, max_value=2099), st.integers(min_value=1, max_value=4)
    ).map(lambda p: f"{p[0]}-Q{p[1]}")
    return st.builds(
        Objective,
        pmdf_version=_pmdf_version_strategy(),
        kind=st.just("objective"),
        id=_id_strategy("obj"),
        provenance=_provenance_strategy(),
        attachments=st.just([]),
        objective=_safe_text(),
        key_results=st.lists(key_result, min_size=1, max_size=3),
        period=period,
        parent_objective=st.none() | _id_strategy("obj"),
    )


def _metric_strategy() -> st.SearchStrategy[Metric]:
    point = st.builds(
        TimeSeriesPoint,
        timestamp=_datetime_strategy(),
        value=st.floats(allow_nan=False, allow_infinity=False, width=32),
    )
    return st.builds(
        Metric,
        pmdf_version=_pmdf_version_strategy(),
        kind=st.just("metric"),
        id=_id_strategy("metric"),
        provenance=_provenance_strategy(),
        attachments=st.just([]),
        name=_safe_text(),
        definition=_safe_text(),
        calculation_method=_safe_text(),
        target_value=st.none() | st.floats(allow_nan=False, allow_infinity=False, width=32),
        threshold_value=st.none() | st.floats(allow_nan=False, allow_infinity=False, width=32),
        current_value=st.none() | st.floats(allow_nan=False, allow_infinity=False, width=32),
        time_series=st.lists(point, max_size=3),
        external_source_url=st.none() | st.just("https://example.com/metric"),
    )


def _roadmap_item_strategy() -> st.SearchStrategy[RoadmapItem]:
    period = st.tuples(
        st.integers(min_value=2020, max_value=2099), st.integers(min_value=1, max_value=4)
    ).map(lambda p: f"{p[0]}-Q{p[1]}")
    return st.builds(
        RoadmapItem,
        pmdf_version=_pmdf_version_strategy(),
        kind=st.just("roadmap_item"),
        id=_id_strategy("roadmap"),
        provenance=_provenance_strategy(),
        attachments=st.just([]),
        product=st.none() | _id_strategy("prod"),
        theme=_safe_text(),
        period=period,
        status=st.sampled_from(["planned", "in_progress", "done", "cancelled"]),
        dependencies=st.lists(_id_strategy("roadmap"), max_size=2),
        objective=_id_strategy("obj"),
    )


def _story_strategy() -> st.SearchStrategy[Story]:
    priority = st.builds(
        Priority,
        method=st.sampled_from(["RICE", "WSJF", "MoSCoW"]),
        reach=st.none() | st.floats(allow_nan=False, allow_infinity=False, width=32),
        impact=st.none() | st.floats(allow_nan=False, allow_infinity=False, width=32),
        confidence=st.none() | st.floats(min_value=0, max_value=1, allow_nan=False, width=32),
        effort=st.none() | st.floats(allow_nan=False, allow_infinity=False, width=32),
        score=st.none() | st.floats(allow_nan=False, allow_infinity=False, width=32),
    )
    links = st.builds(
        StoryLinks,
        objective=st.none() | _id_strategy("obj"),
        decisions=st.lists(_id_strategy("dec"), max_size=2),
    )
    return st.builds(
        Story,
        pmdf_version=_pmdf_version_strategy(),
        kind=st.just("story"),
        id=_id_strategy("story"),
        provenance=_provenance_strategy(),
        attachments=st.just([]),
        product=st.none() | _id_strategy("prod"),
        title=_safe_text(),
        as_a=_safe_text(),
        i_want=_safe_text(),
        so_that=_safe_text(),
        acceptance_criteria=st.lists(_safe_text(), min_size=1, max_size=3),
        priority=priority,
        status=st.sampled_from(["draft", "ready", "in_progress", "done", "dropped"]),
        links=st.none() | links,
    )


def _experiment_strategy() -> st.SearchStrategy[Experiment]:
    return st.builds(
        Experiment,
        pmdf_version=_pmdf_version_strategy(),
        kind=st.just("experiment"),
        id=_id_strategy("experiment"),
        provenance=_provenance_strategy(),
        attachments=st.just([]),
        product=st.none() | _id_strategy("prod"),
        hypothesis=_safe_text(),
        design=_safe_text(),
        success_criteria=st.lists(_safe_text(), min_size=1, max_size=3),
        status=st.sampled_from(["planned", "running", "completed", "aborted"]),
        results=st.none() | _safe_text(),
        learnings=st.none() | _safe_text(),
    )


def _decision_strategy() -> st.SearchStrategy[Decision]:
    option = st.builds(
        Option,
        name=_safe_text(),
        description=st.none() | _safe_text(),
        pros=st.lists(_safe_text(), max_size=2),
        cons=st.lists(_safe_text(), max_size=2),
    )
    rejected = st.builds(RejectedReason, option=_safe_text(), reason=_safe_text())
    return st.builds(
        Decision,
        pmdf_version=_pmdf_version_strategy(),
        kind=st.just("decision"),
        id=_id_strategy("dec"),
        provenance=_provenance_strategy(),
        attachments=st.just([]),
        product=st.none() | _id_strategy("prod"),
        background=_safe_text(),
        options=st.lists(option, min_size=1, max_size=3),
        chosen_option=_safe_text(),
        rationale=_safe_text(),
        rejected_reasons=st.lists(rejected, max_size=2),
        approver=st.none() | _id_strategy("stakeholder"),
        autonomy_level=st.sampled_from(["L0", "L1", "L2", "L3"]),
    )


def _release_strategy() -> st.SearchStrategy[Release]:
    return st.builds(
        Release,
        pmdf_version=_pmdf_version_strategy(),
        kind=st.just("release"),
        id=_id_strategy("release"),
        provenance=_provenance_strategy(),
        attachments=st.just([]),
        product=st.none() | _id_strategy("prod"),
        name=_safe_text(),
        scope=st.lists(_id_strategy("story"), max_size=3),
        go_no_go=st.sampled_from(["go", "no_go", "pending"]),
        released_at=st.none() | _datetime_strategy(),
        actuals=st.just({}),
    )


def _risk_strategy() -> st.SearchStrategy[Risk]:
    return st.builds(
        Risk,
        pmdf_version=_pmdf_version_strategy(),
        kind=st.just("risk"),
        id=_id_strategy("risk"),
        provenance=_provenance_strategy(),
        attachments=st.just([]),
        product=st.none() | _id_strategy("prod"),
        event=_safe_text(),
        probability_score=st.integers(min_value=1, max_value=5),
        impact_score=st.integers(min_value=1, max_value=5),
        response_strategy=st.sampled_from(["avoid", "transfer", "mitigate", "accept"]),
        owner=_id_strategy("stakeholder"),
    )


def _wbs_node_strategy(max_depth: int = 2) -> st.SearchStrategy[WbsNode]:
    children = (
        st.lists(_wbs_node_strategy(max_depth - 1), max_size=2) if max_depth > 0 else st.just([])
    )
    return st.builds(WbsNode, id=_safe_text(max_size=8), name=_safe_text(), children=children)


def _initiative_strategy() -> st.SearchStrategy[Initiative]:
    schedule = st.builds(
        Schedule,
        start_date=st.none() | st.dates(),
        end_date=st.none() | st.dates(),
    )
    evm = st.builds(
        Evm,
        planned_value=st.none() | st.floats(allow_nan=False, allow_infinity=False, width=32),
        earned_value=st.none() | st.floats(allow_nan=False, allow_infinity=False, width=32),
        actual_cost=st.none() | st.floats(allow_nan=False, allow_infinity=False, width=32),
        spi=st.none() | st.floats(allow_nan=False, allow_infinity=False, width=32),
        cpi=st.none() | st.floats(allow_nan=False, allow_infinity=False, width=32),
    )
    return st.builds(
        Initiative,
        pmdf_version=_pmdf_version_strategy(),
        kind=st.just("initiative"),
        id=_id_strategy("initiative"),
        provenance=_provenance_strategy(),
        attachments=st.just([]),
        product=st.none() | _id_strategy("prod"),
        charter=_safe_text(),
        approach=st.sampled_from(["predictive", "adaptive", "hybrid"]),
        wbs=st.lists(_wbs_node_strategy(), max_size=2),
        schedule=st.none() | schedule,
        evm=st.none() | evm,
    )


def _report_strategy() -> st.SearchStrategy[Report]:
    return st.builds(
        Report,
        pmdf_version=_pmdf_version_strategy(),
        kind=st.just("report"),
        id=_id_strategy("report"),
        provenance=_provenance_strategy(),
        attachments=st.just([]),
        product=st.none() | _id_strategy("prod"),
        period=_safe_text(max_size=10),
        health_assessment=st.sampled_from(["green", "yellow", "red"]),
        decisions_needed=st.lists(_safe_text(), max_size=3),
        summary=st.none() | _safe_text(),
    )


def _approval_strategy() -> st.SearchStrategy[Approval]:
    return st.builds(
        Approval,
        pmdf_version=_pmdf_version_strategy(),
        kind=st.just("approval"),
        id=_id_strategy("approval"),
        provenance=_provenance_strategy(),
        attachments=st.just([]),
        target=_id_strategy("dec"),
        proposer=_id_strategy("stakeholder"),
        approver=_id_strategy("stakeholder"),
        decision=st.sampled_from(["approved", "rejected"]),
        reason=_safe_text(),
    )


ENTITY_STRATEGIES: dict[str, st.SearchStrategy] = {
    "product": _product_strategy(),
    "stakeholder": _stakeholder_strategy(),
    "persona": _persona_strategy(),
    "objective": _objective_strategy(),
    "metric": _metric_strategy(),
    "roadmap_item": _roadmap_item_strategy(),
    "story": _story_strategy(),
    "experiment": _experiment_strategy(),
    "decision": _decision_strategy(),
    "release": _release_strategy(),
    "risk": _risk_strategy(),
    "initiative": _initiative_strategy(),
    "report": _report_strategy(),
    "approval": _approval_strategy(),
}


def any_entity_strategy() -> st.SearchStrategy:
    """全kindを対象とした統合戦略(kindごとの偏りなくいずれかを生成する)。"""
    return st.one_of(*ENTITY_STRATEGIES.values())


__all__ = ["ENTITY_STRATEGIES", "any_entity_strategy"]
