import { useCallback, useEffect, useMemo, useReducer, useState } from "react";
import { Link } from "react-router-dom";
import { Aurora, Glass } from "../components/Glass";
import { PeerPicker } from "../components/PeerPicker";
import { RemoteFiles } from "../components/RemoteFiles";
import { SavedFiles } from "../components/SavedFiles";
import { SpeedControl } from "../components/SpeedControl";
import { StatusPill } from "../components/StatusPill";
import { TransferCard } from "../components/TransferCard";
import { downloaderApi, type PeerInfo, type SavedFile } from "../lib/api";
import { initialTransfers, transfersReducer } from "../lib/reducers";
import type { CatalogEntry, DownloadEvent } from "../lib/types";
import { useEventStream } from "../lib/useEventStream";

const messageOf = (error: unknown): string => (error instanceof Error ? error.message : "Something went wrong.");

export function Downloader() {
  const api = useMemo(() => downloaderApi(), []);

  const [peers, setPeers] = useState<PeerInfo[]>([]);
  const [peer, setPeer] = useState<string | null>(null);
  const [remote, setRemote] = useState<CatalogEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [filesError, setFilesError] = useState<string | null>(null);
  const [errors, setErrors] = useState<string[]>([]);
  const [delayMs, setDelayMs] = useState(0);
  const [connections, setConnections] = useState(4);
  const [saved, setSaved] = useState<SavedFile[]>([]);
  const [hashes, setHashes] = useState<Record<string, string>>({});
  const [transfers, dispatch] = useReducer(transfersReducer, undefined, initialTransfers);

  const refreshSaved = useCallback(() => {
    api.saved().then(setSaved).catch((e) => setErrors((prev) => [...prev, messageOf(e)]));
  }, [api]);

  const choosePeer = useCallback(
    (target: string) => {
      setPeer(target);
      setFilesError(null);
      setLoading(true);
      api
        .peerFiles(target)
        .then(setRemote)
        .catch((e) => {
          setRemote([]);
          setFilesError(messageOf(e));
        })
        .finally(() => setLoading(false));
    },
    [api],
  );

  useEffect(() => {
    let cancelled = false;
    api
      .peers()
      .then((list) => {
        if (cancelled) return;
        setPeers(list);
        const first = list.find((p) => p.reachable) ?? list[0];
        if (first) choosePeer(first.label);
      })
      .catch((e) => !cancelled && setFilesError(messageOf(e)));
    refreshSaved();
    return () => {
      cancelled = true;
    };
  }, [api, choosePeer, refreshSaved]);

  const stream = useEventStream<DownloadEvent>(
    api.eventsUrl,
    useCallback(
      (event: DownloadEvent) => {
        dispatch(event);
        if (event.kind === "done") refreshSaved();
      },
      [refreshSaved],
    ),
  );

  const download = (file: CatalogEntry) => {
    if (!peer) return;
    api
      .start({ peer, file_id: file.file_id, connections, chunk_delay_ms: delayMs })
      .then((res) => setHashes((prev) => ({ ...prev, [res.download_id]: file.file_hash })))
      .catch((e) => setErrors((prev) => [...prev, messageOf(e)]));
  };

  const cancel = (downloadId: string) => {
    api.cancel(downloadId).catch((e) => setErrors((prev) => [...prev, messageOf(e)]));
  };

  const deleteSaved = (name: string) => {
    api
      .deleteSaved(name)
      .then(refreshSaved)
      .catch((e) => setErrors((prev) => [...prev, messageOf(e)]));
  };

  const reachable = peers.filter((p) => p.reachable).length;

  return (
    <div className="stage" data-tone="downloader">
      <Aurora />
      <main className="window">
        <header className="window__head">
          <div>
            <h1 className="title">Downloader</h1>
            <p className="subtitle">Pick a peer, choose a file, and watch every chunk get checked on arrival.</p>
          </div>
          <StatusPill stream={stream}>
            {peers.length === 0 ? "Looking for peers…" : `${reachable} of ${peers.length} peers online`}
          </StatusPill>
        </header>

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

        <Glass>
          <h2 className="glass__title">Peer</h2>
          <PeerPicker peers={peers} selected={peer} onSelect={choosePeer} />
        </Glass>

        <Glass>
          <div className="row row--between">
            <h2 className="glass__title">{peer ? `Files on ${peer}` : "Files"}</h2>
            {peer && (
              <button type="button" className="btn btn--quiet" onClick={() => choosePeer(peer)}>
                Refresh list
              </button>
            )}
          </div>
          {filesError ? (
            <p className="error" role="alert">
              {filesError}
            </p>
          ) : (
            <RemoteFiles files={remote} loading={loading} onDownload={download} />
          )}
        </Glass>

        <Glass>
          <h2 className="glass__title">Speed</h2>
          <SpeedControl delayMs={delayMs} connections={connections} onDelay={setDelayMs} onConnections={setConnections} />
        </Glass>

        {transfers.order.length > 0 && (
          <Glass>
            <h2 className="glass__title">Transfers</h2>
            <div className="stack">
              {transfers.order.map((id) => (
                <TransferCard key={id} transfer={transfers.byId[id]} fileHash={hashes[id]} onCancel={cancel} />
              ))}
            </div>
          </Glass>
        )}

        <Glass>
          <h2 className="glass__title">Saved files</h2>
          <SavedFiles files={saved} urlFor={api.savedUrl} onDelete={deleteSaved} />
        </Glass>

        <p className="label">
          <Link to="/">Back to start</Link>
        </p>
      </main>
    </div>
  );
}
