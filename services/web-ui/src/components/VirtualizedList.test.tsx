import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { VirtualizedList } from "./VirtualizedList";

interface Item {
  id: string;
  label: string;
}

function makeItems(count: number): Item[] {
  return Array.from({ length: count }, (_, i) => ({
    id: `item-${i}`,
    label: `活動 ${i}`,
  }));
}

describe("VirtualizedList", () => {
  it("大量件数でもDOMに同時レンダリングされる要素数が全件数より大幅に少ない", () => {
    const items = makeItems(10000);
    render(
      <VirtualizedList
        items={items}
        estimateSize={40}
        height={400}
        renderItem={(item) => <div data-testid="list-row">{item.label}</div>}
        getKey={(item) => item.id}
      />,
    );

    const renderedRows = screen.getAllByTestId("list-row");
    // 表示領域(400px)+ オーバースキャン分のみレンダリングされていること
    // (全件数10000に対して十分小さいこと)を確認する。
    expect(renderedRows.length).toBeGreaterThan(0);
    expect(renderedRows.length).toBeLessThan(100);
  });

  it("件数が0件でもエラーにならない", () => {
    render(
      <VirtualizedList
        items={[]}
        estimateSize={40}
        height={400}
        renderItem={(item: Item) => (
          <div data-testid="list-row">{item.label}</div>
        )}
        getKey={(item: Item) => item.id}
      />,
    );
    expect(screen.queryAllByTestId("list-row")).toHaveLength(0);
  });

  it("先頭アイテムの内容が表示される", () => {
    const items = makeItems(50);
    render(
      <VirtualizedList
        items={items}
        estimateSize={40}
        height={400}
        renderItem={(item) => <div data-testid="list-row">{item.label}</div>}
        getKey={(item) => item.id}
      />,
    );
    expect(screen.getByText("活動 0")).toBeInTheDocument();
  });
});
