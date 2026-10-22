import type { DownloadEvent, PeerEvent } from "./types";

// ---- Downloader -----------------------------------------------------------

export type DownloadStatus = "waiting" | "running" | "verifying" | "done" | "error" | "cancelled";

export interface DownloadState {
  downloadId: string;
  status: DownloadStatus;
  fileName: string;
  fileSize: number;
  chunkCount: number;
  bytesDone: number;
  states: Uint8Array;
  failures: number;
  message: string | null;
  startedAt: number | null;
  finishedAt: number | null;
  lastSeq: number;
}

export function initialDownload(downloadId: string): DownloadState {
  return {
    downloadId,
    status: "waiting",
    fileName: "",
    fileSize: 0,
    chunkCount: 0,
    bytesDone: 0,
    states: new Uint8Array(0),
    failures: 0,
    message: null,
    startedAt: null,
    finishedAt: null,
    lastSeq: 0,
  };
}

export function downloadReducer(state: DownloadState, event: DownloadEvent): DownloadState {
  if (event.download_id !== state.downloadId || event.seq <= state.lastSeq) return state;
  const next: DownloadState = {
    ...state,
    lastSeq: event.seq,
    fileName: event.file_name || state.fileName,
    fileSize: event.file_size || state.fileSize,
    bytesDone: event.bytes_done,
  };

  switch (event.kind) {
    case "manifest":
      return {
        ...next,
        status: "running",
        chunkCount: event.chunk_count,
        states: new Uint8Array(event.chunk_count),
        startedAt: event.ts,
      };
    case "chunk_ok":
    case "chunk_failed": {
      const states = state.states.slice();
      if (event.index !== null && event.index < states.length) {
        states[event.index] = event.kind === "chunk_ok" ? 2 : 3;
      }
      return {
        ...next,
        states,
        failures: state.failures + (event.kind === "chunk_failed" ? 1 : 0),
        message: event.kind === "chunk_failed" ? event.message : state.message,
      };
    }
    case "verifying":
      return { ...next, status: "verifying" };
    case "done":
      return { ...next, status: "done", finishedAt: event.ts };
    case "error":
      return { ...next, status: "error", message: event.message, finishedAt: event.ts };
    case "cancelled":
      return { ...next, status: "cancelled", finishedAt: event.ts };
    default:
      return next;
  }
}

// ---- Uploader -------------------------------------------------------------

export interface LogLine {
  seq: number;
  ts: number;
  text: string;
}

export interface ServedFile {
  name: string;
  chunkCount: number;
  states: Uint8Array;
}

export interface ServingState {
  files: Record<string, ServedFile>;
  log: LogLine[];
  connections: number;
  lastSeq: number;
}

const MAX_LOG_LINES = 200;

export function initialServing(): ServingState {
  return { files: {}, log: [], connections: 0, lastSeq: 0 };
}

export function describePeerEvent(e: PeerEvent): string {
  const name = e.file_name ?? "a file";
  const index = (e.index ?? 0) + 1;
  switch (e.kind) {
    case "connect":
      return `Connection opened from ${e.remote}`;
    case "disconnect":
      return "Connection closed";
    case "catalog":
      return "Someone asked for the file list";
    case "manifest":
      return `Someone asked for the details of ${name}`;
    case "chunk":
      return `Sent chunk ${index} of ${e.chunk_count ?? "?"} · ${name}`;
    case "tamper_served":
      return `Sent a corrupted copy of chunk ${index} · ${name} (on purpose)`;
    case "refresh":
      return "Rescanned the shared folder";
  }
}

export function servingReducer(state: ServingState, event: PeerEvent): ServingState {
  if (event.seq <= state.lastSeq) return state;
  let { files, connections } = state;

  if (event.kind === "connect") connections += 1;
  if (event.kind === "disconnect") connections = Math.max(0, connections - 1);

  if (event.file_id && event.chunk_count !== null) {
    const existing = files[event.file_id];
    const fresh = !existing || existing.chunkCount !== event.chunk_count || event.kind === "manifest";
    const states = fresh ? new Uint8Array(event.chunk_count) : existing.states.slice();
    if ((event.kind === "chunk" || event.kind === "tamper_served") && event.index !== null) {
      if (event.index < states.length) states[event.index] = event.kind === "chunk" ? 2 : 3;
    }
    files = {
      ...files,
      [event.file_id]: { name: event.file_name ?? existing?.name ?? "", chunkCount: event.chunk_count, states },
    };
  }

  const log = [{ seq: event.seq, ts: event.ts, text: describePeerEvent(event) }, ...state.log].slice(0, MAX_LOG_LINES);
  return { files, log, connections, lastSeq: event.seq };
}

// ---- Several downloads at once -------------------------------------------

export interface TransfersState {
  /** Download ids, newest first. */
  order: string[];
  byId: Record<string, DownloadState>;
}

export function initialTransfers(): TransfersState {
  return { order: [], byId: {} };
}

export function transfersReducer(state: TransfersState, event: DownloadEvent): TransfersState {
  const known = state.byId[event.download_id];
  const next = downloadReducer(known ?? initialDownload(event.download_id), event);
  if (known && next === known) return state;
  return {
    order: known ? state.order : [event.download_id, ...state.order],
    byId: { ...state.byId, [event.download_id]: next },
  };
}
