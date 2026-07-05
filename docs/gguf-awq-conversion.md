# GGUF / AWQ 変換手順 (MR-04)

Tier-L ローカル推論(Ollama)および Tier-S vLLM 向けのモデル変換手順。
実変換は GPU 環境が必要なため CI 対象外。

## GGUF (Ollama 向け)

1. LoRA アダプタをベースモデルにマージする (transformers + peft)
2. `llama.cpp` の `convert_hf_to_gguf.py` で GGUF を生成
3. 必要に応じて `quantize` で Q4_K_M 等に量子化
4. `ollama create` で Modelfile からカスタムモデルを登録

```bash
# 例 (パスは環境に合わせて調整)
python convert_hf_to_gguf.py /path/to/merged-model --outfile pdm-student.gguf
ollama create pdm-student-promoted -f Modelfile
```

## AWQ / GPTQ (vLLM 向け)

1. マージ済み HF モデルを用意
2. `autoawq` または `auto-gptq` で 4bit 量子化
3. vLLM の `--quantization awq` でサーバ起動

```bash
# AWQ 例
python -m awq.entry --model_path /path/to/merged --w_bit 4 --q_group_size 128
vllm serve /path/to/awq-model --quantization awq
```

## 注意

- 変換前に eval-runner の昇格ゲート (`compare_models`) を通過したアダプタのみ使用すること
- シークレット・API キーは Modelfile やスクリプトに直書きしない
