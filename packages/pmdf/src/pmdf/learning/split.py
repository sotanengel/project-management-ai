"""E8-1: 学習データ split 割当。"""

from __future__ import annotations

from collections import defaultdict

from pmdf.learning.contamination import HashableScenario, resolve_scenario_hash


def assign_split[RecordT: HashableScenario](
    records: list[RecordT],
    ratios: dict[str, float] | None = None,
) -> dict[str, list[RecordT]]:
    """レコードを train/val/gate に分割する。

    同一 `scenario_hash` のレコードは必ず同一 split に配置する。
    """
    split_ratios = ratios or {"train": 0.8, "val": 0.1, "gate": 0.1}
    split_names = list(split_ratios.keys())
    grouped: dict[str, list[RecordT]] = defaultdict(list)
    for record in records:
        grouped[resolve_scenario_hash(record)].append(record)

    ordered_hashes = sorted(grouped.keys())
    total_groups = len(ordered_hashes)
    if total_groups == 0:
        return {name: [] for name in split_names}

    boundaries: list[int] = []
    cumulative = 0.0
    for name in split_names[:-1]:
        cumulative += split_ratios[name]
        boundaries.append(int(total_groups * cumulative))
    boundaries.append(total_groups)

    result: dict[str, list[RecordT]] = {name: [] for name in split_names}
    start = 0
    for name, end in zip(split_names, boundaries, strict=True):
        for scenario_hash in ordered_hashes[start:end]:
            result[name].extend(grouped[scenario_hash])
        start = end
    return result
