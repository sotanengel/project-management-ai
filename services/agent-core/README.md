# agent-core

PdM AIエージェントの実行基盤(E5)。LangGraphによるグラフ実行、
model-gateway経由のLLMクライアント、タスクキュー、緊急停止照会、
PMDF/RAGツール群、業務グラフ(バックログ/ビジョン・ロードマップ・
リリース判断/KPI監視・Decision Record・週次レビュー/ディスカバリー・
実験・ステークホルダー調整・施策実行)、根拠明示・差戻フィードバック
取込、チャット指示インターフェースを実装する。

詳細は `docs/IMPLEMENTATION_STATE.md` の「agent-core 公開インター
フェース」セクションを参照。
