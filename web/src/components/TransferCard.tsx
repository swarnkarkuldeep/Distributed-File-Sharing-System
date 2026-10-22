import { formatBytes } from "../lib/format";
import type { DownloadState } from "../lib/reducers";
import { Mosaic } from "./Mosaic";

interface Props {
  transfer: DownloadState;
  fileHash?: string;
  onCancel: (downloadId: string) => void;
}

const HEADLINE: Record<DownloadState["status"], string> = {
  waiting: "Starting…",
  running: "Downloading",
  verifying: "Checking the whole file…",
  done: "Downloaded and verified",
  error: "Download failed",
  cancelled: "Cancelled",
};

export function TransferCard({ transfer, fileHash, onCancel }: Props) {
  const name = transfer.fileName || "File";
  const verified = transfer.states.reduce((n, s) => n + (s === 2 ? 1 : 0), 0);
  const active = transfer.status === "waiting" || transfer.status === "running" || transfer.status === "verifying";
  const took =
    transfer.startedAt !== null && transfer.finishedAt !== null
      ? Math.max(0, transfer.finishedAt - transfer.startedAt)
      : null;

  return (
    <article className="stack" aria-label={`Transfer of ${name}`}>
      <div className="row row--between">
        <div>
          <h3 className="file__name">{name}</h3>
          <p className={`verdict ${transfer.status === "done" ? "verdict--ok" : ""}`}>{HEADLINE[transfer.status]}</p>
        </div>
        {active && (
          <button
            type="button"
            className="btn btn--quiet btn--danger"
            aria-label={`Cancel ${name}`}
            onClick={() => onCancel(transfer.downloadId)}
          >
            Cancel
          </button>
        )}
      </div>

      <Mosaic states={transfer.states} label={name} emptyText="Waiting for the file details…" />

      <div className="transfer__stats">
        <div className="stat">
          <span className="label">Verified</span>
          <span className="stat__value">
            {verified} of {transfer.chunkCount}
          </span>
        </div>
        <div className="stat">
          <span className="label">Failed hash checks</span>
          <span className={`stat__value ${transfer.failures > 0 ? "stat__value--bad" : ""}`}>{transfer.failures}</span>
        </div>
        <div className="stat">
          <span className="label">Transferred</span>
          <span className="stat__value">
            {formatBytes(transfer.bytesDone)} of {formatBytes(transfer.fileSize)}
          </span>
        </div>
        {took !== null && transfer.status === "done" && (
          <div className="stat">
            <span className="label">Took</span>
            <span className="stat__value">{took.toFixed(1)} s</span>
          </div>
        )}
      </div>

      {active && transfer.failures > 0 && transfer.message && (
        <p className="label" role="status">
          {transfer.message}
        </p>
      )}
      {transfer.status === "error" && (
        <p className="error" role="alert">
          {transfer.message ?? "Something went wrong."} Nothing was saved. Start the download again to retry.
        </p>
      )}
      {transfer.status === "done" && fileHash && (
        <p className="hash mono">SHA-256 {fileHash} matched the file you asked for.</p>
      )}
    </article>
  );
}
