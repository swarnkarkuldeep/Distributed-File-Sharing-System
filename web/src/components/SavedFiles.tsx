import { formatBytes } from "../lib/format";
import type { SavedFile } from "../lib/api";

interface Props {
  files: SavedFile[];
  urlFor: (name: string) => string;
  onDelete: (name: string) => void;
}

export function SavedFiles({ files, urlFor, onDelete }: Props) {
  if (files.length === 0) return <p className="empty">Nothing saved yet. Finished downloads show up here.</p>;
  return (
    <ul className="files">
      {files.map((file) => (
        <li key={file.name} className="file">
          <span className="file__name">{file.name}</span>
          <span className="file__meta">{formatBytes(file.size)} · verified</span>
          <span className="file__actions">
            <a className="btn" href={urlFor(file.name)} download={file.name} aria-label={`Save ${file.name} to this computer`}>
              Save to this computer
            </a>
            <button
              type="button"
              className="btn btn--quiet btn--danger"
              aria-label={`Delete ${file.name}`}
              onClick={() => onDelete(file.name)}
            >
              Delete
            </button>
          </span>
        </li>
      ))}
    </ul>
  );
}
