import { useState } from "react";
import type { PeerInfo } from "../lib/api";

interface Props {
  peers: PeerInfo[];
  selected: string | null;
  onSelect: (peer: string) => void;
}

export function PeerPicker({ peers, selected, onSelect }: Props) {
  const [custom, setCustom] = useState("");

  return (
    <div className="stack">
      <div className="row" role="group" aria-label="Peers">
        {peers.map((peer) => (
          <button
            key={peer.label}
            type="button"
            className={`btn ${selected === peer.label ? "btn--primary" : ""}`}
            aria-pressed={selected === peer.label}
            onClick={() => onSelect(peer.label)}
          >
            <span className={`dot ${peer.reachable ? "dot--live" : "dot--down"}`} aria-hidden="true" /> {peer.label}
            <span className="visually-hidden">{peer.reachable ? " (online)" : " (offline)"}</span>
          </button>
        ))}
      </div>
      <form
        className="row"
        onSubmit={(e) => {
          e.preventDefault();
          if (custom.trim()) onSelect(custom.trim());
        }}
      >
        <input
          className="field field--grow"
          aria-label="Peer address"
          placeholder="Another peer, as host:port"
          value={custom}
          onChange={(e) => setCustom(e.target.value)}
        />
        <button type="submit" className="btn" disabled={!custom.trim()}>
          Connect
        </button>
      </form>
    </div>
  );
}
