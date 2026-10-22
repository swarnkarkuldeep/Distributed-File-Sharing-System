import type { StreamStatus } from "../lib/useEventStream";

interface Props {
  stream: StreamStatus;
  children: React.ReactNode;
}

/** Connection dot plus a short line of text. The dot pings while the event stream is open. */
export function StatusPill({ stream, children }: Props) {
  const live = stream === "open";
  return (
    <p className="pill" role="status">
      <span className={`dot ${live ? "dot--live" : stream === "reconnecting" ? "dot--down" : ""}`} aria-hidden="true" />
      <span>{stream === "reconnecting" ? "Reconnecting to the app server…" : children}</span>
    </p>
  );
}
