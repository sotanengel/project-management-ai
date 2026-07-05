import { useEffect, useRef } from "react";

export interface WsEvent {
  type: string;
  data: unknown;
}

interface UseWebSocketOptions {
  /** 接続先URL。`null`の場合は接続を試みない(未認証時)。 */
  url: string | null;
  onMessage: (event: WsEvent) => void;
  onOpen?: () => void;
  onClose?: () => void;
}

const INITIAL_RETRY_DELAY_MS = 1000;
const MAX_RETRY_DELAY_MS = 30000;

/**
 * `/ws/events`への接続を管理するフック。
 *
 * 切断時は指数バックオフ(1秒→2秒→4秒→…上限30秒)で自動再接続する。
 * `url`が`null`(未認証)の間は接続を試みない。
 */
export function useWebSocket({
  url,
  onMessage,
  onOpen,
  onClose,
}: UseWebSocketOptions): void {
  const retryDelayRef = useRef(INITIAL_RETRY_DELAY_MS);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const socketRef = useRef<WebSocket | null>(null);
  const isUnmountedRef = useRef(false);

  // 最新のコールバックを常に参照できるようにrefへ保持する(接続確立処理を
  // 依存配列に含めず、urlが変わらない限り再接続ループを再構築しないため)。
  const onMessageRef = useRef(onMessage);
  const onOpenRef = useRef(onOpen);
  const onCloseRef = useRef(onClose);
  onMessageRef.current = onMessage;
  onOpenRef.current = onOpen;
  onCloseRef.current = onClose;

  useEffect(() => {
    isUnmountedRef.current = false;

    if (!url) {
      return () => {
        isUnmountedRef.current = true;
      };
    }

    function connect() {
      if (isUnmountedRef.current || !url) {
        return;
      }
      const socket = new WebSocket(url);
      socketRef.current = socket;

      socket.onopen = () => {
        retryDelayRef.current = INITIAL_RETRY_DELAY_MS;
        onOpenRef.current?.();
      };

      socket.onmessage = (event: MessageEvent) => {
        try {
          const parsed = JSON.parse(event.data as string) as WsEvent;
          onMessageRef.current(parsed);
        } catch {
          // 不正なペイロードは無視する
        }
      };

      socket.onclose = () => {
        onCloseRef.current?.();
        if (isUnmountedRef.current) {
          return;
        }
        const delay = retryDelayRef.current;
        retryDelayRef.current = Math.min(
          retryDelayRef.current * 2,
          MAX_RETRY_DELAY_MS,
        );
        reconnectTimerRef.current = setTimeout(connect, delay);
      };
    }

    connect();

    return () => {
      isUnmountedRef.current = true;
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
      }
      socketRef.current?.close();
    };
  }, [url]);
}
