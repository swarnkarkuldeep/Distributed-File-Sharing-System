import type { CatalogEntry, TamperState } from "./types";

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

function detailOf(body: unknown, fallback: string): string {
  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail) && detail.length > 0) {
      const first = detail[0] as { msg?: string };
      if (first?.msg) return first.msg;
    }
  }
  return fallback;
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(url, init);
  } catch {
    throw new ApiError("Can't reach the app server. Check that the containers are running.", 0);
  }
  if (response.status === 204) return undefined as T;
  let body: unknown = null;
  try {
    body = await response.json();
  } catch {
    /* no JSON body */
  }
  if (!response.ok) throw new ApiError(detailOf(body, response.statusText || "Request failed"), response.status);
  return body as T;
}

const json = (method: string, body?: unknown): RequestInit => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: body === undefined ? undefined : JSON.stringify(body),
});

export type UploaderNode = "uploader" | "uploader2";

export interface UploaderStatus {
  role: "uploader";
  peer_port: number;
  chunk_size: number;
  file_count: number;
  tamper: TamperState | null;
}

export function uploaderApi(node: UploaderNode) {
  const base = `/api/${node}`;
  return {
    eventsUrl: `${base}/events`,
    status: () => request<UploaderStatus>(`${base}/status`),
    files: () => request<CatalogEntry[]>(`${base}/files`),
    remove: (fileId: string) => request<void>(`${base}/files/${fileId}`, { method: "DELETE" }),
    arm: (body: TamperState) => request<TamperState>(`${base}/tamper`, json("PUT", body)),
    disarm: () => request<{ armed: false }>(`${base}/tamper`, { method: "DELETE" }),
    /** Uses XMLHttpRequest because fetch cannot report upload progress. */
    upload(file: File, onProgress?: (fraction: number) => void): Promise<CatalogEntry> {
      return new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        xhr.open("POST", `${base}/files`);
        xhr.upload.onprogress = (e) => {
          if (e.lengthComputable && onProgress) onProgress(e.loaded / e.total);
        };
        xhr.onload = () => {
          let body: unknown = null;
          try {
            body = JSON.parse(xhr.responseText);
          } catch {
            /* no JSON body */
          }
          if (xhr.status >= 200 && xhr.status < 300) resolve(body as CatalogEntry);
          else reject(new ApiError(`${file.name}: ${detailOf(body, "upload failed")}`, xhr.status));
        };
        xhr.onerror = () => reject(new ApiError(`${file.name}: can't reach the app server`, 0));
        const form = new FormData();
        form.append("file", file);
        xhr.send(form);
      });
    },
  };
}

export interface PeerInfo {
  label: string;
  host: string;
  port: number;
  reachable: boolean;
  file_count: number;
}

export interface StartDownloadBody {
  peer: string;
  file_id: string;
  connections: number;
  chunk_delay_ms: number;
}

export interface SavedFile {
  name: string;
  size: number;
}

export function downloaderApi() {
  const base = "/api/downloader";
  return {
    eventsUrl: `${base}/events`,
    peers: () => request<PeerInfo[]>(`${base}/peers`),
    peerFiles: (peer: string) => request<CatalogEntry[]>(`${base}/peers/files?peer=${encodeURIComponent(peer)}`),
    start: (body: StartDownloadBody) =>
      request<{ download_id: string; file_name: string }>(`${base}/downloads`, json("POST", body)),
    cancel: (id: string) => request<unknown>(`${base}/downloads/${id}`, { method: "DELETE" }),
    saved: () => request<SavedFile[]>(`${base}/saved`),
    deleteSaved: (name: string) => request<void>(`${base}/saved/${encodeURIComponent(name)}`, { method: "DELETE" }),
    savedUrl: (name: string) => `${base}/saved/${encodeURIComponent(name)}`,
  };
}

export type DownloaderApi = ReturnType<typeof downloaderApi>;
export type UploaderApi = ReturnType<typeof uploaderApi>;
