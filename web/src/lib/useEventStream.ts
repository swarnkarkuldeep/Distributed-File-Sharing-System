import { useEffect, useRef, useState } from "react";

export type StreamStatus = "connecting" | "open" | "reconnecting";

/**
 * Subscribe to a server-sent event stream. The browser reconnects by itself and sends
 * Last-Event-ID, so the server replays what was missed; events are de-duplicated by seq.
 */
export function useEventStream<T extends { seq: number }>(url: string, onEvent: (event: T) => void): StreamStatus {
  const [status, setStatus] = useState<StreamStatus>("connecting");
  const handler = useRef(onEvent);
  handler.current = onEvent;

  useEffect(() => {
    let lastSeq = 0;
    const source = new EventSource(url);
    source.onopen = () => setStatus("open");
    source.onerror = () => setStatus("reconnecting");
    source.onmessage = (message) => {
      try {
        const event = JSON.parse(message.data) as T;
        if (event.seq <= lastSeq) return;
        lastSeq = event.seq;
        handler.current(event);
      } catch {
        /* ignore malformed events */
      }
    };
    return () => source.close();
  }, [url]);

  return status;
}
