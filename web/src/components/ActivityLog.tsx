import type { LogLine } from "../lib/reducers";

function clock(ts: number): string {
  return new Date(ts * 1000).toLocaleTimeString([], { hour12: false });
}

export function ActivityLog({ lines, emptyText }: { lines: LogLine[]; emptyText: string }) {
  if (lines.length === 0) return <p className="empty">{emptyText}</p>;
  return (
    <ul className="log" aria-label="Activity" aria-live="off">
      {lines.map((line) => (
        <li key={line.seq} className="log__line">
          <span className="log__time">{clock(line.ts)}</span>
          <span>{line.text}</span>
        </li>
      ))}
    </ul>
  );
}
