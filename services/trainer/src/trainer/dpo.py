"""E8-7: TRL DPO トレーナー。"""

from __future__ import annotations

import json
from pathlib import Path

import mlflow
from datasets import Dataset
from peft import LoraConfig, get_peft_model
from trl import DPOConfig, DPOTrainer

from trainer.bnb_adapter import load_model_4bit, load_model_standard, load_tokenizer
from trainer.config import TrainingConfig


def _configure_mlflow(
    mlflow_tracking_uri: str | None,
    output_dir: Path,
) -> None:
    if mlflow_tracking_uri:
        mlflow.set_tracking_uri(mlflow_tracking_uri)
    else:
        db_path = output_dir / "mlflow.db"
        mlflow.set_tracking_uri(f"sqlite:///{db_path.as_posix()}")


def _load_dpo_dataset(path: Path) -> Dataset:
    rows: list[dict[str, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return Dataset.from_list(rows)


def run_dpo(
    dataset_path: str | Path,
    config: TrainingConfig,
    *,
    resume_from_checkpoint: str | None = None,
    mlflow_tracking_uri: str | None = None,
) -> Path:
    """DPO 学習を実行し、最終 checkpoint パスを返す。"""
    dataset_path = Path(dataset_path)
    output_dir = Path(config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if mlflow_tracking_uri:
        _configure_mlflow(mlflow_tracking_uri, output_dir)
    else:
        _configure_mlflow(None, output_dir)
    mlflow.set_experiment(config.mlflow_experiment)

    with mlflow.start_run():
        mlflow.log_params(config.model_dump())

        if config.use_4bit:
            base_model = load_model_4bit(config.model_name)
        else:
            base_model = load_model_standard(config.model_name)

        tokenizer = load_tokenizer(config.model_name)
        lora = LoraConfig(
            r=config.lora_rank,
            lora_alpha=config.lora_rank * 2,
            lora_dropout=0.05,
            task_type="CAUSAL_LM",
        )
        model = get_peft_model(base_model, lora)

        dataset = _load_dpo_dataset(dataset_path)

        training_args = DPOConfig(
            output_dir=str(output_dir),
            max_steps=config.max_steps,
            save_steps=config.save_steps,
            per_device_train_batch_size=config.per_device_train_batch_size,
            learning_rate=config.learning_rate,
            logging_steps=1,
            save_total_limit=2,
            report_to=[],
            use_cpu=not __import__("torch").cuda.is_available(),
            max_length=config.seq_len,
        )

        trainer = DPOTrainer(
            model=model,  # type: ignore[arg-type]
            args=training_args,
            train_dataset=dataset,
            processing_class=tokenizer,
        )

        train_result = trainer.train(resume_from_checkpoint=resume_from_checkpoint)
        checkpoint = output_dir / f"checkpoint-{train_result.global_step}"
        trainer.save_model(str(checkpoint))
        mlflow.log_param("checkpoint_path", str(checkpoint))
        mlflow.log_metric("train_steps", float(train_result.global_step))

    return checkpoint


def main() -> None:
    import sys

    if len(sys.argv) < 2:
        raise SystemExit("usage: trainer-dpo <dataset.jsonl>")
    run_dpo(sys.argv[1], TrainingConfig())
