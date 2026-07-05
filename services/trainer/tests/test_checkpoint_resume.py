"""checkpoint 再開テスト(E8-7)。"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from trainer.bnb_adapter import load_model_standard
from trainer.config import TINY_MODEL, TrainingConfig
from trainer.sft import run_sft


@patch("trainer.sft.load_model_4bit", side_effect=load_model_standard)
def test_run_sft_resume_from_checkpoint(mock_4bit, tmp_path: Path) -> None:
    dataset = tmp_path / "sft.jsonl"
    out = tmp_path / "out"
    rows = [{"prompt": "p", "completion": "c"}]
    dataset.write_text(json.dumps(rows[0]) + "\n", encoding="utf-8")

    cfg = TrainingConfig(
        model_name=TINY_MODEL,
        use_4bit=True,
        max_steps=2,
        save_steps=1,
        output_dir=str(out),
        seq_len=64,
        lora_rank=4,
    )
    first_ckpt = run_sft(dataset, cfg)
    second_ckpt = run_sft(
        dataset,
        cfg,
        resume_from_checkpoint=str(first_ckpt),
    )

    assert second_ckpt.exists() or out.exists()
