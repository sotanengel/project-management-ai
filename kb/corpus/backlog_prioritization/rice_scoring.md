---
domain: backlog_prioritization
framework: rice
pm_principle: null
title: RICEスコアによる優先順位付けの考え方
source: original
license: internal
---

RICEスコアは、施策候補を「Reach(到達範囲)」「Impact(影響度)」
「Confidence(確信度)」「Effort(工数)」の4要素で見積もり、
(Reach × Impact × Confidence) ÷ Effort で相対スコアを算出する
優先順位付け手法である。異なる性質の施策同士を同じ物差しで比較
できる点が実務上のメリットになる。

運用上の注意点として、各要素の見積もりはどうしても主観に左右される
ため、チーム内で見積もり基準(例えばReachは向こう1四半期で影響を
受けるユーザー数、Confidenceはデータの裏付け有無に応じた3段階評価)
を事前にすり合わせておくことが望ましい。またEffortを過小評価すると
スコアが不当に高く出るため、実装だけでなく検証・運用コストも含めて
見積もる。RICEはあくまで議論を構造化するための道具であり、
スコアの僅差だけで機械的に優劣を決めるのではなく、戦略適合度など
スコア化しにくい要素と合わせて判断するのが実践的である。
