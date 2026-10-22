import { formatBytes, shortHash } from "../lib/format";
import type { CatalogEntry } from "../lib/types";

interface Props {
  files: CatalogEntry[];
  selectedId: string | null;
  onSelect: (fileId: string) => void;
  onRemove: (file: CatalogEntry) => void;
}

export function FileList({ files, selectedId, onSelect, onRemove }: Props) {
  return (
    <ul className="files">
      {files.map((file) => (
        <li key={file.file_id} className={`file ${file.file_id === selectedId ? "file--selected" : ""}`}>
          <button
            type="button"
            className="btn btn--quiet file__name"
            style={{ textAlign: "left", padding: 0 }}
            aria-pressed={file.file_id === selectedId}
            onClick={() => onSelect(file.file_id)}
          >
            {file.file_name}
          </button>
          <span className="file__meta">
            {formatBytes(file.file_size)} · {file.chunk_count} {file.chunk_count === 1 ? "chunk" : "chunks"} ·{" "}
            <span className="mono">{shortHash(file.file_id)}</span>
            {file.aliases.length > 0 && <> · also named {file.aliases.join(", ")}</>}
          </span>
          <span className="file__actions">
            <button
              type="button"
              className="btn btn--quiet btn--danger"
              aria-label={`Stop sharing ${file.file_name}`}
              onClick={() => onRemove(file)}
            >
              Stop sharing
            </button>
          </span>
        </li>
      ))}
    </ul>
  );
}
