export type ChunkState = 0 | 1 | 2 | 3; // pending, active, verified, failed

export interface CatalogEntry {
  file_id: string;
  file_name: string;
  file_size: number;
  chunk_size: number;
  file_hash: string;
  chunk_count: number;
  aliases: string[];
}

export type PeerEventKind =
  | "connect"
  | "disconnect"
  | "catalog"
  | "manifest"
  | "chunk"
  | "refresh"
  | "tamper_served";

export interface PeerEvent {
  type: "peer";
  seq: number;
  ts: number;
  kind: PeerEventKind;
  remote: string;
  file_id: string | null;
  file_name: string | null;
  index: number | null;
  chunk_count: number | null;
}

export interface FileEvent {
  type: "file";
  seq: number;
  ts: number;
  kind: "added" | "removed";
  file: CatalogEntry;
}

export interface TamperEvent {
  type: "tamper";
  seq: number;
  ts: number;
  armed: boolean;
  file_id: string | null;
  index: number | null;
  once: boolean;
}

export type UploaderEvent = PeerEvent | FileEvent | TamperEvent;

export type DownloadEventKind =
  | "manifest"
  | "resumed"
  | "chunk_ok"
  | "chunk_failed"
  | "verifying"
  | "done"
  | "error"
  | "cancelled";

export interface DownloadEvent {
  type: "download";
  seq: number;
  ts: number;
  download_id: string;
  kind: DownloadEventKind;
  index: number | null;
  chunk_count: number;
  bytes_done: number;
  file_size: number;
  file_name: string;
  message: string | null;
}

export interface TamperState {
  file_id: string;
  index: number;
  once: boolean;
}
