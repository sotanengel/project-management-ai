"""SFT smoke テスト(E8-7)。"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import mlflow
from trainer.bnb_adapter import load_model_standard
from trainer.config import TINY_MODEL, TrainingConfig
from trainer.sft import run_sft


def _write_sft_dataset(path: Path) -> None:
    rows = [
        {"prompt": "Q: 優先順位は?", "completion": "A: RICEで判断"},
        {"prompt": "Q: リリース?", "completion": "A: Go"},
    ]
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


@patch("trainer.sft.load_model_4bit", side_effect=load_model_standard)
def test_run_sft_smoke(mock_4bit, tmp_path: Path) -> None:
    """bnb モック + tiny モデルで SFT が完走する。"""
    dataset = tmp_path / "sft.jsonl"
    out = tmp_path / "out"
    _write_sft_dataset(dataset)

    cfg = TrainingConfig(
        model_name=TINY_MODEL,
        use_4bit=True,
        max_steps=1,
        save_steps=1,
        output_dir=str(out),
        seq_len=64,
        lora_rank=4,
    )
    checkpoint = run_sft(
        dataset,
        cfg,
    )

    mock_4bit.assert_called_once()
    assert checkpoint.exists() or out.exists()
    runs = mlflow.search_runs(experiment_names=["pdm-trainer"])
    assert len(runs) >= 1
