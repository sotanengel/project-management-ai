import { useRef, type ReactNode } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import styles from "./VirtualizedList.module.css";

interface VirtualizedListProps<T> {
  items: T[];
  /** 各行の推定高さ(px)。 */
  estimateSize: number;
  /** 表示領域の高さ(px)。 */
  height: number;
  renderItem: (item: T, index: number) => ReactNode;
  getKey: (item: T, index: number) => string;
  /** 表示領域外に追加でレンダリングする行数(既定5)。 */
  overscan?: number;
}

/**
 * `@tanstack/react-virtual`を用いた仮想化リスト。
 *
 * NFR-02(エンティティ1万件規模で初期表示3秒以内)を満たすため、
 * 表示領域内(+オーバースキャン分)のみDOMにレンダリングする。
 */
export function VirtualizedList<T>({
  items,
  estimateSize,
  height,
  renderItem,
  getKey,
  overscan = 5,
}: VirtualizedListProps<T>) {
  const parentRef = useRef<HTMLDivElement>(null);

  const virtualizer = useVirtualizer({
    count: items.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => estimateSize,
    overscan,
    // jsdom(テスト環境)ではResizeObserverがスクロールコンテナの実寸を
    // 報告しないため、`initialRect`で表示領域高さを明示的に与える
    // (本番のブラウザ環境では実測値で上書きされるため影響しない)。
    initialRect: { width: 0, height },
  });

  const virtualItems = virtualizer.getVirtualItems();

  return (
    <div
      ref={parentRef}
      className={styles.scrollContainer}
      style={{ height }}
      data-testid="virtualized-list-container"
    >
      <div
        style={{
          height: virtualizer.getTotalSize(),
          position: "relative",
          width: "100%",
        }}
      >
        {virtualItems.map((virtualRow) => {
          const item = items[virtualRow.index];
          return (
            <div
              key={getKey(item, virtualRow.index)}
              data-index={virtualRow.index}
              style={{
                position: "absolute",
                top: 0,
                left: 0,
                width: "100%",
                height: virtualRow.size,
                transform: `translateY(${virtualRow.start}px)`,
              }}
            >
              {renderItem(item, virtualRow.index)}
            </div>
          );
        })}
      </div>
    </div>
  );
}
