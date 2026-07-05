import { describe, expect, it } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { http, HttpResponse } from "msw";
import { server } from "../test/server";
import { API_BASE_URL } from "../api/client";
import { EntityEditor } from "./EntityEditor";

const STORY_ENTITY = {
  kind: "story",
  id: "story-01",
  title: "検索機能の改善",
  as_a: "ユーザーとして",
  i_want: "検索したい",
  so_that: "見つけたい",
  acceptance_criteria: ["既存の検索結果と一致すること"],
  priority: { method: "RICE" },
  status: "draft",
};

function renderEditor(initialPath = "/edit/story/story-01") {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialPath]}>
        <Routes>
          <Route path="/edit/:kind/:id" element={<EntityEditor />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("EntityEditor", () => {
  it("フォームモードでstoryの受入基準を追加し保存すると、PUTが呼ばれる", async () => {
    server.use(
      http.get(`${API_BASE_URL}/pmdf/story/story-01`, () =>
        HttpResponse.json(STORY_ENTITY),
      ),
      http.put(`${API_BASE_URL}/pmdf/story/story-01`, async ({ request }) => {
        const body = (await request.json()) as Record<string, unknown>;
        expect(
          (body.acceptance_criteria as string[]).includes("新しい受入基準"),
        ).toBe(true);
        return HttpResponse.json({ ...STORY_ENTITY, ...body });
      }),
    );

    const user = userEvent.setup();
    renderEditor();

    await waitFor(() => {
      expect(screen.getByTestId("entity-editor-form")).toBeInTheDocument();
    });

    await user.type(screen.getByLabelText("新しい受入基準"), "新しい受入基準");
    await user.click(screen.getByRole("button", { name: "追加" }));
    await user.click(screen.getByRole("button", { name: "保存" }));

    await waitFor(() => {
      expect(screen.getByTestId("entity-editor-success")).toBeInTheDocument();
    });
  });

  it("保存時にスキーマ検証エラー(422)が返るとフィールド単位でエラーメッセージが表示される", async () => {
    server.use(
      http.get(`${API_BASE_URL}/pmdf/story/story-01`, () =>
        HttpResponse.json(STORY_ENTITY),
      ),
      http.put(`${API_BASE_URL}/pmdf/story/story-01`, () =>
        HttpResponse.json(
          { detail: "スキーマ検証エラー: 'as_a' is a required property" },
          { status: 422 },
        ),
      ),
    );

    const user = userEvent.setup();
    renderEditor();

    await waitFor(() => {
      expect(screen.getByTestId("entity-editor-form")).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: "保存" }));

    await waitFor(() => {
      expect(screen.getByTestId("entity-editor-error")).toHaveTextContent(
        "'as_a' is a required property",
      );
    });
  });

  it("YAML/JSONエディタモードに切り替え、不正な入力を行うと保存ボタンが無効化される", async () => {
    server.use(
      http.get(`${API_BASE_URL}/pmdf/story/story-01`, () =>
        HttpResponse.json(STORY_ENTITY),
      ),
    );

    const user = userEvent.setup();
    renderEditor();

    await waitFor(() => {
      expect(screen.getByTestId("entity-editor-form")).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: "YAML/JSONエディタ" }));

    const textarea = await screen.findByRole("textbox");
    fireEvent.change(textarea, { target: { value: "{invalid json" } });

    expect(screen.getByRole("button", { name: "保存" })).toBeDisabled();
  });
});
