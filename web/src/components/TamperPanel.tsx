import { useState } from "react";
import type { CatalogEntry, TamperState } from "../lib/types";

interface Props {
  selected: CatalogEntry | null;
  tamper: TamperState | null;
  error: string | null;
  onArm: (index: number, once: boolean) => void;
  onDisarm: () => void;
}

/** Lets the presenter send one chunk with a flipped byte, so the downloader's hash check has something to catch. */
export function TamperPanel({ selected, tamper, error, onArm, onDisarm }: Props) {
  return (
    <div className="stack">
      <p className="label">
        Send one chunk with a flipped byte. The downloader should reject it and fetch that chunk again.
      </p>
      {selected ? (
        <TamperForm key={selected.file_id} selected={selected} tamper={tamper} onArm={onArm} onDisarm={onDisarm} />
      ) : (
        <p className="empty">Share a file first, then pick a chunk to corrupt.</p>
      )}
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}

function TamperForm({ selected, tamper, onArm, onDisarm }: Omit<Props, "error"> & { selected: CatalogEntry }) {
  const [index, setIndex] = useState(Math.floor(selected.chunk_count / 2));
  const armedHere = tamper && tamper.file_id === selected.file_id;
  const empty = selected.chunk_count === 0;

  return (
    <>
      <div className="row">
        <label className="label" htmlFor="tamper-chunk">
          Chunk number
        </label>
        <input
          id="tamper-chunk"
          className="field"
          type="number"
          min={1}
          max={Math.max(1, selected.chunk_count)}
          value={index + 1}
          disabled={empty}
          onChange={(e) => {
            const n = Math.round(Number(e.target.value)) - 1;
            if (Number.isFinite(n)) setIndex(Math.min(Math.max(0, n), Math.max(0, selected.chunk_count - 1)));
          }}
          style={{ width: "7rem" }}
        />
        <span className="label">of {selected.chunk_count}</span>
      </div>
      <div className="row">
        <button type="button" className="btn btn--primary" disabled={empty} onClick={() => onArm(index, true)}>
          Corrupt this chunk once
        </button>
        <button type="button" className="btn" disabled={empty} onClick={() => onArm(index, false)}>
          Corrupt every time
        </button>
        {tamper && (
          <button type="button" className="btn btn--quiet" onClick={onDisarm}>
            Stop corrupting
          </button>
        )}
      </div>
      {armedHere && (
        <p role="status" className="label">
          Chunk {tamper.index + 1} of {selected.file_name} will be sent corrupted
          {tamper.once ? " once." : " every time."}
        </p>
      )}
      {empty && <p className="empty">This file has no chunks to corrupt.</p>}
    </>
  );
}
