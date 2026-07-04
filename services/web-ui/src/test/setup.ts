import "@testing-library/jest-dom/vitest";
import { afterAll, afterEach, beforeAll } from "vitest";
import { server } from "./server";

// jsdomにはResizeObserverが実装されていないため、rechartsの
// ResponsiveContainerや@tanstack/react-virtualが依存する最小限のスタブを
// グローバルに提供する。
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}

if (typeof globalThis.ResizeObserver === "undefined") {
  globalThis.ResizeObserver =
    ResizeObserverStub as unknown as typeof ResizeObserver;
}

// jsdomは`offsetWidth`/`offsetHeight`を常に0として返すため、
// @tanstack/react-virtualの仮想化計算(表示領域サイズの実測)が機能しない。
// テスト環境限定で、要素のインラインstyle上のheight/widthを反映した値を
// 返すよう上書きする(仮想化リストのテストで実際の表示件数を検証するため)。
function readPixelStyle(
  element: HTMLElement,
  prop: "height" | "width",
): number {
  const value = element.style[prop];
  const parsed = Number.parseFloat(value);
  return Number.isNaN(parsed) ? 0 : parsed;
}

Object.defineProperty(HTMLElement.prototype, "offsetHeight", {
  configurable: true,
  get(this: HTMLElement) {
    return readPixelStyle(this, "height");
  },
});

Object.defineProperty(HTMLElement.prototype, "offsetWidth", {
  configurable: true,
  get(this: HTMLElement) {
    return readPixelStyle(this, "width") || 1000;
  },
});

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
