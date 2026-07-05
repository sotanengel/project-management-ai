import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  BUSINESS_FUNCTIONS,
  getEmergencyStopStatus,
  listAutonomyLevels,
  listPmdfEntities,
  releaseEmergencyStop,
  sendChatInstruction,
  setAutonomyLevel,
  triggerEmergencyStop,
  type AutonomyLevel,
} from "../api/client";
import type { Product } from "../api/pmdfTypes";
import { useAuth } from "../auth/useAuth";
import { getRoleFromToken } from "../auth/jwt";
import { useAppState } from "../state/useAppState";
import styles from "./AgentControl.module.css";

const LEVELS: AutonomyLevel[] = ["L0", "L1", "L2", "L3"];

const STATUS_LABELS: Record<string, string> = {
  pending: "受付済み",
  running: "実行中",
  done: "完了",
  failed: "失敗",
};

const BUSINESS_FUNCTION_LABELS: Record<string, string> = {
  vision: "ビジョン",
  roadmap: "ロードマップ",
  discovery: "ディスカバリー",
  backlog: "バックログ",
  kpi_monitoring: "KPI監視",
  experiment: "実験",
  release: "リリース",
  decision_record: "DR",
  stakeholder: "SH調整",
  initiative: "施策",
  periodic_review: "定期レビュー",
};

function resolveLevel(
  configs: Array<{
    product_id: string;
    business_function: string;
    level: AutonomyLevel;
  }>,
  productId: string,
  businessFunction: string,
): AutonomyLevel {
  const found = configs.find(
    (entry) =>
      entry.product_id === productId &&
      entry.business_function === businessFunction,
  );
  return found?.level ?? "L0";
}

/** エージェント制御画面(FR-UI-07, FR-AU-05)。 */
export function AgentControl() {
  const { token } = useAuth();
  const role = getRoleFromToken(token);
  const isAdmin = role === "admin";
  const queryClient = useQueryClient();
  const { recentActivity } = useAppState();

  const [chatMessage, setChatMessage] = useState("");
  const [chatProductId, setChatProductId] = useState("");
  const [lastTaskId, setLastTaskId] = useState<string | null>(null);

  const productsQuery = useQuery({
    queryKey: ["pmdf", "product"],
    queryFn: () => listPmdfEntities<Product>("product"),
  });

  const autonomyQuery = useQuery({
    queryKey: ["autonomy"],
    queryFn: () => listAutonomyLevels(),
  });

  const emergencyQuery = useQuery({
    queryKey: ["autonomy", "emergency-stop"],
    queryFn: () => getEmergencyStopStatus(),
  });

  const products = productsQuery.data ?? [];
  const autonomyConfigs = autonomyQuery.data ?? [];
  const emergencyStopped =
    emergencyQuery.data?.emergency_stopped ?? false;

  useEffect(() => {
    const list = productsQuery.data;
    if (chatProductId === "" && list && list.length > 0) {
      setChatProductId(list[0].id);
    }
  }, [chatProductId, productsQuery.data]);

  const levelMutation = useMutation({
    mutationFn: ({
      productId,
      businessFunction,
      level,
    }: {
      productId: string;
      businessFunction: string;
      level: AutonomyLevel;
    }) => setAutonomyLevel(productId, businessFunction, level),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["autonomy"] });
    },
  });

  const chatMutation = useMutation({
    mutationFn: () =>
      sendChatInstruction({
        message: chatMessage,
        product_id: chatProductId,
      }),
    onSuccess: (task) => {
      setLastTaskId(task.id);
      setChatMessage("");
    },
  });

  const stopMutation = useMutation({
    mutationFn: () => triggerEmergencyStop(),
    onSuccess: (data) => {
      queryClient.setQueryData(["autonomy", "emergency-stop"], data);
    },
  });

  const releaseMutation = useMutation({
    mutationFn: () => releaseEmergencyStop(),
    onSuccess: (data) => {
      queryClient.setQueryData(["autonomy", "emergency-stop"], data);
    },
  });

  const taskStatus = useMemo(() => {
    if (!lastTaskId) {
      return null;
    }
    const event = recentActivity.find((item) => item.task_id === lastTaskId);
    return event?.status ?? "pending";
  }, [lastTaskId, recentActivity]);

  function handleLevelChange(
    productId: string,
    businessFunction: string,
    level: AutonomyLevel,
  ) {
    if (!isAdmin) {
      return;
    }
    levelMutation.mutate({ productId, businessFunction, level });
  }

  function handleEmergencyStop() {
    if (!isAdmin) {
      return;
    }
    if (!window.confirm("エージェントの自律実行を緊急停止しますか？")) {
      return;
    }
    stopMutation.mutate();
  }

  return (
    <div className={styles.container}>
      <h1>エージェント制御</h1>

      {emergencyStopped && (
        <div
          className={styles.emergencyBanner}
          data-testid="emergency-stop-banner"
        >
          緊急停止中 — エージェントの自律実行は停止されています
        </div>
      )}

      <section className={styles.section}>
        <h2>自律レベル設定</h2>
        {!isAdmin && (
          <p className={styles.adminNote}>
            自律レベルの変更は管理者(admin)のみ可能です。現在の設定を参照できます。
          </p>
        )}
        {levelMutation.isError && (
          <p className={styles.error} role="alert">
            自律レベルの保存に失敗しました
          </p>
        )}
        <div className={styles.matrixWrapper} data-testid="autonomy-matrix">
          <table className={styles.matrix}>
            <thead>
              <tr>
                <th>プロダクト</th>
                {BUSINESS_FUNCTIONS.map((bf) => (
                  <th key={bf}>{BUSINESS_FUNCTION_LABELS[bf] ?? bf}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {products.map((product) => (
                <tr key={product.id}>
                  <td className={styles.productCell}>{product.name}</td>
                  {BUSINESS_FUNCTIONS.map((bf) => {
                    const level = resolveLevel(
                      autonomyConfigs,
                      product.id,
                      bf,
                    );
                    const labelId = `${product.id} ${bf}`;
                    return (
                      <td key={bf}>
                        <select
                          className={styles.levelSelect}
                          aria-label={labelId}
                          value={level}
                          disabled={!isAdmin || levelMutation.isPending}
                          onChange={(event) =>
                            handleLevelChange(
                              product.id,
                              bf,
                              event.target.value as AutonomyLevel,
                            )
                          }
                        >
                          {LEVELS.map((option) => (
                            <option key={option} value={option}>
                              {option}
                            </option>
                          ))}
                        </select>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className={styles.section}>
        <h2>チャット指示</h2>
        <form
          className={styles.chatForm}
          onSubmit={(event) => {
            event.preventDefault();
            if (chatMessage.trim().length === 0 || chatProductId === "") {
              return;
            }
            chatMutation.mutate();
          }}
        >
          <div className={styles.field}>
            <label htmlFor="chat-product">プロダクト</label>
            <select
              id="chat-product"
              value={chatProductId}
              onChange={(event) => setChatProductId(event.target.value)}
            >
              {products.map((product) => (
                <option key={product.id} value={product.id}>
                  {product.name}
                </option>
              ))}
            </select>
          </div>
          <div className={styles.field}>
            <label htmlFor="chat-message">指示メッセージ</label>
            <textarea
              id="chat-message"
              rows={3}
              value={chatMessage}
              onChange={(event) => setChatMessage(event.target.value)}
            />
          </div>
          <button type="submit" disabled={chatMutation.isPending}>
            指示を送信
          </button>
        </form>
        {lastTaskId && (
          <p className={styles.taskStatus} data-testid="chat-task-status">
            タスク {lastTaskId}:{" "}
            {STATUS_LABELS[taskStatus ?? "pending"] ?? taskStatus}
          </p>
        )}
        {chatMutation.isError && (
          <p className={styles.error} role="alert">
            チャット指示の送信に失敗しました
          </p>
        )}
      </section>

      <section className={styles.section}>
        <h2>緊急停止</h2>
        <div className={styles.emergencyActions}>
          <button
            type="button"
            className={styles.dangerButton}
            disabled={!isAdmin || emergencyStopped || stopMutation.isPending}
            onClick={handleEmergencyStop}
          >
            緊急停止
          </button>
          {isAdmin && emergencyStopped && (
            <button
              type="button"
              className={styles.releaseButton}
              disabled={releaseMutation.isPending}
              onClick={() => releaseMutation.mutate()}
            >
              緊急停止を解除
            </button>
          )}
        </div>
        {!isAdmin && (
          <p className={styles.adminNote}>
            緊急停止の操作は管理者(admin)のみ実行できます。
          </p>
        )}
      </section>
    </div>
  );
}
