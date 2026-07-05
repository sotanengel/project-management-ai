"""TrainingConfig テスト。"""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from trainer.config import TINY_MODEL, TrainingConfig


def test_training_config_defaults_within_tier_l() -> None:
    cfg = TrainingConfig()
    assert cfg.lora_rank <= 16
    assert cfg.seq_len <= 2048
    assert cfg.model_name == TINY_MODEL


def test_training_config_rejects_lora_rank_over_16() -> None:
    with pytest.raises(ValidationError, match="lora_rank"):
        TrainingConfig(lora_rank=32)


def test_training_config_rejects_seq_len_over_2048() -> None:
    with pytest.raises(ValidationError, match="seq_len"):
        TrainingConfig(seq_len=4096)
