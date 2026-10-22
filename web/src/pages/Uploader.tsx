import { useCallback, useEffect, useMemo, useReducer, useState } from "react";
import { Link } from "react-router-dom";
import { ActivityLog } from "../components/ActivityLog";
import { Dropzone } from "../components/Dropzone";
import { FileList } from "../components/FileList";
import { Aurora, Glass } from "../components/Glass";
import { Mosaic } from "../components/Mosaic";
import { ProgressBar } from "../components/ProgressBar";
import { StatusPill } from "../components/StatusPill";
import { TamperPanel } from "../components/TamperPanel";
import { ApiError, uploaderApi, type UploaderNode, type UploaderStatus } from "../lib/api";
import { initialServing, servingReducer } from "../lib/reducers";
import type { CatalogEntry, TamperState, UploaderEvent } from "../lib/types";
import { useEventStream } from "../lib/useEventStream";

interface UploadItem {
  id: number;
  name: string;
  progress: number;
}

const messageOf = (error: unknown): string => (error instanceof Error ? error.message : "Something went wrong.");

function upsert(files: CatalogEntry[], entry: CatalogEntry): CatalogEntry[] {
  return files.some((f) => f.file_id === entry.file_id)
    ? files.map((f) => (f.file_id === entry.file_id ? entry : f))
    : [...files, entry];
}

export function Uploader({ node }: { node: UploaderNode }) {
  const api = useMemo(() => uploaderApi(node), [node]);
  const label = node === "uploader2" ? "Uploader 2" : "Uploader";

  const [status, setStatus] = useState<UploaderStatus | null>(null);
  const [files, setFiles] = useState<CatalogEntry[]>([]);
  const [tamper, setTamper] = useState<TamperState | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [uploads, setUploads] = useState<UploadItem[]>([]);
  const [errors, setErrors] = useState<string[]>([]);
  const [tamperError, setTamperError] = useState<string | null>(null);
  const [serving, dispatch] = useReducer(servingReducer, undefined, initialServing);

  useEffect(() => {
    let cancelled = false;
    Promise.all([api.status(), api.files()])
      .then(([s, f]) => {
        if (cancelled) return;
        setStatus(s);
        setTamper(s.tamper);
        setFiles((current) => f.reduce(upsert, current));
      })
      .catch((e) => !cancelled && setErrors((prev) => [...prev, messageOf(e)]));
    return () => {
      cancelled = true;
    };
  }, [api]);

  const stream = useEventStream<UploaderEvent>(
    api.eventsUrl,
    useCallback((event: UploaderEvent) => {
      if (event.type === "peer") dispatch(event);
      else if (event.type === "file") {
        setFiles((current) =>
          event.kind === "added" ? upsert(current, event.file) : current.filter((f) => f.file_id !== event.file.file_id),
        );
      } else if (event.type === "tamper") {
        setTamper(event.armed && event.file_id !== null && event.index !== null
          ? { file_id: event.file_id, index: event.index, once: event.once }
          : null);
      }
    }, []),
  );

  const selected = files.find((f) => f.file_id === selectedId) ?? files[0] ?? null;
  const selectedStates = useMemo(
    () => (selected ? (serving.files[selected.file_id]?.states ?? new Uint8Array(selected.chunk_count)) : new Uint8Array(0)),
    [selected, serving.files],
  );

  const share = useCallback(
    (picked: File[]) => {
      for (const file of picked) {
        const id = Date.now() + Math.random();
        setUploads((prev) => [...prev, { id, name: file.name, progress: 0 }]);
        api
          .upload(file, (progress) =>
            setUploads((prev) => prev.map((u) => (u.id === id ? { ...u, progress } : u))),
          )
          .then((entry) => {
            setFiles((current) => upsert(current, entry));
            setSelectedId(entry.file_id);
          })
          .catch((e) => setErrors((prev) => [...prev, messageOf(e)]))
          .finally(() => setUploads((prev) => prev.filter((u) => u.id !== id)));
      }
    },
    [api],
  );

  const remove = (file: CatalogEntry) => {
    api
      .remove(file.file_id)
      .then(() => setFiles((current) => current.filter((f) => f.file_id !== file.file_id)))
      .catch((e) => setErrors((prev) => [...prev, messageOf(e)]));
  };

  const arm = (index: number, once: boolean) => {
    if (!selected) return;
    setTamperError(null);
    api
      .arm({ file_id: selected.file_id, index, once })
      .then(setTamper)
      .catch((e: ApiError) => setTamperError(e.message));
  };

  const disarm = () => {
    setTamperError(null);
    api
      .disarm()
      .then(() => setTamper(null))
      .catch((e: ApiError) => setTamperError(e.message));
  };

  return (
    <div className="stage" data-tone="uploader">
      <Aurora />
      <main className="window">
        <header className="window__head">
          <div>
            <h1 className="title">{label}</h1>
            <p className="subtitle">Share files from this window. The downloader fetches them in verified chunks.</p>
          </div>
          <StatusPill stream={stream}>
            {status ? `Sharing on port ${status.peer_port}` : "Starting up…"} · {files.length}{" "}
            {files.length === 1 ? "file" : "files"}
            {serving.connections > 0 && ` · ${serving.connections} connected`}
          </StatusPill>
        </header>

        <Glass>
          <div className="stack">
            <Dropzone onFiles={share} hasFiles={files.length > 0} />
            {uploads.map((u) => (
              <div key={u.id} className="stack">
                <span className="label">Sharing {u.name}…</span>
                <ProgressBar value={Math.round(u.progress * 100)} max={100} label={`Uploading ${u.name}`} />
              </div>
            ))}
            {errors.map((message, i) => (
              <div key={i} className="error row row--between" role="alert">
                <span>{message}</span>
                <button
                  type="button"
                  className="btn btn--quiet"
                  onClick={() => setErrors((prev) => prev.filter((_, j) => j !== i))}
                >
                  Dismiss
                </button>
              </div>
            ))}
          </div>
        </Glass>

        {files.length > 0 && (
          <Glass>
            <h2 className="glass__title">Shared files</h2>
            <div className="stack">
              <FileList files={files} selectedId={selected?.file_id ?? null} onSelect={setSelectedId} onRemove={remove} />
              {selected && (
                <>
                  <h3 className="label">Chunks sent for {selected.file_name}</h3>
                  <Mosaic
                    states={selectedStates}
                    label={selected.file_name}
                    emptyText="This file has no chunks. It is empty."
                  />
                </>
              )}
            </div>
          </Glass>
        )}

        <Glass>
          <h2 className="glass__title">Corrupt a chunk</h2>
          <TamperPanel selected={selected} tamper={tamper} error={tamperError} onArm={arm} onDisarm={disarm} />
        </Glass>

        <Glass>
          <h2 className="glass__title">Activity</h2>
          <ActivityLog lines={serving.log} emptyText="Nothing yet. Activity appears when the downloader connects." />
        </Glass>

        <p className="label">
          <Link to="/">Back to start</Link>
        </p>
      </main>
    </div>
  );
}
