interface Props {
  delayMs: number;
  connections: number;
  onDelay: (ms: number) => void;
  onConnections: (n: number) => void;
}

export function SpeedControl({ delayMs, connections, onDelay, onConnections }: Props) {
  return (
    <div className="stack">
      <div className="row">
        <label className="label" htmlFor="demo-speed">
          Demo speed: {delayMs === 0 ? "Instant" : `${delayMs} ms pause per chunk`}
        </label>
        <input
          id="demo-speed"
          className="range"
          type="range"
          min={0}
          max={200}
          step={10}
          value={delayMs}
          onChange={(e) => onDelay(Number(e.target.value))}
        />
      </div>
      <div className="row">
        <label className="label" htmlFor="connections">
          Parallel connections
        </label>
        <input
          id="connections"
          className="field"
          style={{ width: "5rem" }}
          type="number"
          min={1}
          max={8}
          value={connections}
          onChange={(e) => onConnections(Math.min(8, Math.max(1, Math.round(Number(e.target.value)) || 1)))}
        />
      </div>
      <p className="label">Local transfers finish in milliseconds. Slow them down to watch each chunk get checked.</p>
    </div>
  );
}
