import type {
  Decision,
  Metric,
  PmdfEntityBase,
  RoadmapItem,
  Story,
} from "../../api/pmdfTypes";
import { StoryView } from "./StoryView";
import { DecisionView } from "./DecisionView";
import { RoadmapItemView } from "./RoadmapItemView";
import { MetricView } from "./MetricView";
import { GenericEntityView } from "./GenericEntityView";

/**
 * PMDF全14 kindのエンティティを、kind別のレンダリングコンポーネントに
 * 振り分けて表示するディスパッチャ(FR-UI-03)。
 *
 * story/decision/roadmap_item/metricは専用ビューを持ち、それ以外の10種は
 * 汎用キー値表示(`GenericEntityView`)にフォールバックする。
 */
export function EntityView({ entity }: { entity: Record<string, unknown> }) {
  switch (entity.kind) {
    case "story":
      return <StoryView entity={entity as unknown as Story} />;
    case "decision":
      return <DecisionView entity={entity as unknown as Decision} />;
    case "roadmap_item":
      return <RoadmapItemView entity={entity as unknown as RoadmapItem} />;
    case "metric":
      return <MetricView entity={entity as unknown as Metric} />;
    default:
      return <GenericEntityView entity={entity as unknown as PmdfEntityBase} />;
  }
}
