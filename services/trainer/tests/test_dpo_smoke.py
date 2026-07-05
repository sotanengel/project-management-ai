"""DPO smoke テスト(E8-7)。"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from trainer.bnb_adapter import load_model_standard
from trainer.config import TINY_MODEL, TrainingConfig
from trainer.dpo import run_dpo


def _write_dpo_dataset(path: Path) -> None:
    rows = [
        {
            "prompt": "判断せよ",
            "chosen": "良い回答",
            "rejected": "悪い回答",
        }
    ]
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


@patch("trainer.dpo.load_model_4bit", side_effect=load_model_standard)
def test_run_dpo_smoke(mock_4bit, tmp_path: Path) -> None:
    dataset = tmp_path / "dpo.jsonl"
    out = tmp_path / "out"
    _write_dpo_dataset(dataset)

    cfg = TrainingConfig(
        model_name=TINY_MODEL,
        use_4bit=True,
        max_steps=1,
        save_steps=1,
        output_dir=str(out),
        seq_len=64,
        lora_rank=4,
    )
    checkpoint = run_dpo(dataset, cfg)

    mock_4bit.assert_called_once()
    assert checkpoint.exists() or out.exists()
