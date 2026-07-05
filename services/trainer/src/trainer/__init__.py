"""E8-7: QLoRA trainer パッケージ。"""

from trainer.config import TINY_MODEL, TrainingConfig
from trainer.dpo import run_dpo
from trainer.sft import run_sft

__all__ = ["TINY_MODEL", "TrainingConfig", "run_dpo", "run_sft"]
