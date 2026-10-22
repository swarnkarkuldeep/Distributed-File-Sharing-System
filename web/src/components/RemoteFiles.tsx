import { formatBytes } from "../lib/format";
import type { CatalogEntry } from "../lib/types";

interface Props {
  files: CatalogEntry[];
  loading: boolean;
  onDownload: (file: CatalogEntry) => void;
}

export function RemoteFiles({ files, loading, onDownload }: Props) {
  if (loading) return <p className="empty">Loading the file list…</p>;
  if (files.length === 0) return <p className="empty">This peer isn't sharing anything yet.</p>;
  return (
    <ul className="files">
      {files.map((file) => (
        <li key={file.file_id} className="file">
          <span className="file__name">{file.file_name}</span>
          <span className="file__meta">
            {formatBytes(file.file_size)} · {file.chunk_count} {file.chunk_count === 1 ? "chunk" : "chunks"}
          </span>
          <span className="file__actions">
            <button
              type="button"
              className="btn btn--primary"
              aria-label={`Download ${file.file_name}`}
              onClick={() => onDownload(file)}
            >
              Download
            </button>
          </span>
        </li>
      ))}
    </ul>
  );
}
