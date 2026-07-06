# ローカル検証チェックリスト (人手)

GPU 実機または長時間実行が必要な受け入れ基準 (AC-03 / AC-04 / AC-10) の
人手検証手順です。CI ではモック・スキップとし、リリース前に本チェックリストで
記録を残してください。

## 記録テンプレート

| 項目  | 実施日 | 実施者 | 結果 (Pass/Fail) | 備考 |
| ----- | ------ | ------ | ---------------- | ---- |
| AC-03 |        |        |                  |      |
| AC-04 |        |        |                  |      |
| AC-10 |        |        |                  |      |

---

## AC-03: 自己学習ループ 1 周無人完走

**前提**: `local-gpu` またはクラウド GPU、`train` profile、予算内、サンプルシード投入済み

1. [ ] `docker compose --profile api-only --profile train up -d`
2. [ ] scheduler の `trigger_learning_loop()` を手動または cron で 1 回実行
3. [ ] 各段階がログに記録されること
   - synthesize_scenarios → execute_scenario → hybrid_evaluate
   - build_sft_dataset / build_dpo_dataset → trainer → eval-runner compare
4. [ ] 予算超過時はループがスキップされること (E9-2)
5. [ ] MLflow UI で run が記録されること

**合格**: 上記が中断なく完了し、eval-runner の compare 結果が保存される。

---

## AC-04: 評価ゲート閾値判定

**前提**: E8 eval-runner ベンチマーク 300 問、昇格ゲート設定済み

1. [ ] `eval-runner compare` を実行し JSON/レポートを取得
2. [ ] 閾値 (例: 勝率・スコア差) を満たす場合のみ `promotion` 相当の判定が true
3. [ ] 閾値未満の場合は昇格せず、ログに理由が残ること
4. [ ] 結果を issue または週次レビューに添付

**合格**: 閾値ロジックが仕様どおり分岐し、証跡が残る。

---

## AC-10: 7B Q4 推論 VRAM 8GB 内・100 ターン安定

**前提**: `local-gpu`、7B クラス Q4 量子化モデル、NVidia GPU 8GB 級

1. [ ] `nvidia-smi` でアイドル VRAM を記録
2. [ ] Ollama (または同等) で対象モデルをロード
3. [ ] 監督 UI または API から同一セッションで **100 ターン** 連続チャット
4. [ ] 各ターン後に OOM・クラッシュ・応答欠落がないこと
5. [ ] ピーク VRAM が 8GB 以内であること (`nvidia-smi` ログ保存)

**合格**: 100 ターン完走、ピーク VRAM ≤ 8GB、エラー 0 件。

---

## 参考コマンド

```bash
# 学習ループ手動 (scheduler コンテナ内)
docker compose exec scheduler uv run python -c \
  "from scheduler.jobs import trigger_learning_loop; trigger_learning_loop()"

# 評価比較
docker compose --profile train run --rm eval-runner compare --help

# GPU 監視 (WSL2)
watch -n 1 nvidia-smi
```
