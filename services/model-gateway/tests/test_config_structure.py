"""litellm.config.yaml の静的構造検証(E4-1)。

LiteLLMパッケージそのものはpmdfが要求するtyperバージョンと競合するため
(litellm 1.90.2はtyper<0.26系を要求し、pmdfはtyper>=0.26.8を要求)、
ワークスペース全体のlockfileを壊さないようlitellmはPython依存として
追加しない。そのため本テストはYAML構造の静的検証に留める
(イシューE4-1本文の「重い場合はYAML構造検証のみで可」を採用)。
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

CONFIG_PATH = Path(__file__).parent.parent / "litellm.config.yaml"

REQUIRED_LOGICAL_NAMES = {"pdm-main", "pdm-teacher", "pdm-judge", "pdm-embed"}


def load_config() -> dict:
    with CONFIG_PATH.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_config_file_exists() -> None:
    assert CONFIG_PATH.is_file()


def test_config_has_model_list() -> None:
    config = load_config()
    assert "model_list" in config
    assert isinstance(config["model_list"], list)
    assert len(config["model_list"]) > 0


def test_all_required_logical_names_are_defined() -> None:
    """AR-01: pdm-main/pdm-teacher/pdm-judge/pdm-embedの4論理名が定義済み。"""
    config = load_config()
    model_names = {entry["model_name"] for entry in config["model_list"]}
    assert REQUIRED_LOGICAL_NAMES.issubset(model_names)


@pytest.mark.parametrize("logical_name", sorted(REQUIRED_LOGICAL_NAMES))
def test_each_logical_name_has_required_keys(logical_name: str) -> None:
    """各エントリが`litellm_params.model`を必須キーとして持つ。"""
    config = load_config()
    entries = [e for e in config["model_list"] if e["model_name"] == logical_name]
    assert len(entries) >= 1
    for entry in entries:
        assert "litellm_params" in entry
        assert "model" in entry["litellm_params"]


def test_no_hardcoded_api_keys() -> None:
    """APIキーが直書きされておらず、環境変数参照(os.environ/...)のみであることを確認する。"""
    config = load_config()
    for entry in config["model_list"]:
        params = entry["litellm_params"]
        api_key = params.get("api_key")
        if api_key is not None:
            assert isinstance(api_key, str)
            assert api_key.startswith(
                "os.environ/"
            ), f"{entry['model_name']}: api_keyは環境変数参照のみ許可されます: {api_key!r}"


def test_no_plausible_hardcoded_secret_values() -> None:
    """設定全体をダンプした文字列に、実キーらしき文字列(sk-等)が含まれないことを確認する。"""
    raw_text = CONFIG_PATH.read_text(encoding="utf-8")
    forbidden_prefixes = ["sk-ant-", "sk-proj-", "sk-", "AKIA"]
    for prefix in forbidden_prefixes:
        assert prefix not in raw_text, f"直書きされたシークレットらしき文字列を検出: {prefix}"


def test_supports_anthropic_openai_bedrock_ollama_backends() -> None:
    """AR-02: Anthropic/OpenAI/Bedrock/Ollama互換ローカルサーバの4種を最低限サポートする。

    実モデル名・エンドポイントは`os.environ/VAR_NAME`経由で注入されるため
    YAML自体には現れない。各プロバイダ用のクレデンシャル注入キー
    (api_key/aws_*/api_base)がエントリ群に存在することで、4バックエンドを
    設定上サポートしていることを検証する。
    """
    config = load_config()
    all_param_keys: set[str] = set()
    for entry in config["model_list"]:
        all_param_keys.update(entry["litellm_params"].keys())

    # Anthropic/OpenAI: api_key経由(os.environ/ANTHROPIC_API_KEY, OPENAI_API_KEY)。
    api_key_refs = {
        entry["litellm_params"]["api_key"]
        for entry in config["model_list"]
        if "api_key" in entry["litellm_params"]
    }
    assert "os.environ/ANTHROPIC_API_KEY" in api_key_refs
    assert "os.environ/OPENAI_API_KEY" in api_key_refs

    # Bedrock: aws_access_key_id等の専用キーで識別。
    assert "aws_access_key_id" in all_param_keys
    assert "aws_secret_access_key" in all_param_keys

    # Ollama(OpenAI互換ローカルサーバ): api_baseで識別、pdm-main-localが該当。
    local_entry = next(e for e in config["model_list"] if e["model_name"] == "pdm-main-local")
    assert "api_base" in local_entry["litellm_params"]


def test_env_driven_backend_switch_uses_env_var_placeholders() -> None:
    """.env切替(オンラインAPI⇄ローカルOllama)のため、model/api_baseが`os.environ/`参照
    経由であり、実バックエンド名・実URLがYAMLに直書きされていないことを確認する。
    `pdm-main`(オンライン既定)と`pdm-main-local`(ローカルOllama切替例)の両方が
    定義されていること。
    """
    config = load_config()
    model_names = {entry["model_name"] for entry in config["model_list"]}
    assert "pdm-main" in model_names
    assert "pdm-main-local" in model_names

    for entry in config["model_list"]:
        model = entry["litellm_params"]["model"]
        assert model.startswith(
            "os.environ/"
        ), f"{entry['model_name']}: modelは環境変数参照であること: {model!r}"
        api_base = entry["litellm_params"].get("api_base")
        if api_base is not None:
            assert api_base.startswith("os.environ/")
