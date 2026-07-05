"""E8-7: QLoRA トレーナー設定。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

TINY_MODEL = "hf-internal-testing/tiny-random-GPT2LMHeadModel"


class TrainingConfig(BaseModel):
    """Tier-L 既定に沿った学習設定。"""

    model_config = ConfigDict(extra="forbid")

    model_name: str = TINY_MODEL
    lora_rank: int = Field(default=8, ge=1)
    seq_len: int = Field(default=128, ge=1)
    use_4bit: bool = True
    gradient_checkpointing: bool = True
    max_steps: int = Field(default=2, ge=1)
    save_steps: int = Field(default=1, ge=1)
    learning_rate: float = 5e-5
    per_device_train_batch_size: int = 1
    output_dir: str = "outputs/checkpoints"
    mlflow_experiment: str = "pdm-trainer"

    @model_validator(mode="after")
    def validate_tier_l_limits(self) -> TrainingConfig:
        if self.lora_rank > 16:
            raise ValueError("lora_rank は Tier-L 既定で 16 以下である必要があります")
        if self.seq_len > 2048:
            raise ValueError("seq_len は Tier-L 既定で 2048 以下である必要があります")
        return self
