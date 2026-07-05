"""bitsandbytes 4bit ロードの関数境界ラッパー(E8-7)。

CPU/CI 環境ではテストで本関数をモックし、通常の `from_pretrained` に
フォールバックさせる。
"""

from __future__ import annotations

from typing import Any, cast

from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    PreTrainedModel,
    PreTrainedTokenizerBase,
)


def load_model_4bit(model_name: str, **kwargs: Any) -> PreTrainedModel:
    """4bit 量子化ロード(本番 GPU 環境用)。

    bitsandbytes 未搭載環境では ImportError を送出する。
    テストでは `@patch` で差し替えること。
    """
    try:
        from transformers import BitsAndBytesConfig
    except ImportError as exc:
        raise ImportError("bitsandbytes/transformers quantization が利用できません") from exc

    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype="float16",
    )
    return cast(
        PreTrainedModel,
        AutoModelForCausalLM.from_pretrained(
            model_name,
            quantization_config=bnb_config,
            device_map="auto",
            **kwargs,
        ),
    )


def load_tokenizer(model_name: str) -> PreTrainedTokenizerBase:
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token or "<pad>"
    return tokenizer


def load_model_standard(model_name: str, **kwargs: Any) -> PreTrainedModel:
    """4bit 無効時の通常ロード(CPU smoke 用)。"""
    return cast(PreTrainedModel, AutoModelForCausalLM.from_pretrained(model_name, **kwargs))
