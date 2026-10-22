/**
 * Collapse per-chunk states (0 pending, 1 active, 2 verified, 3 failed) into at most
 * `maxTiles` tiles. A tile is failed if any member failed, verified only when every
 * member is verified, active when any member is active or verified, otherwise pending.
 */
export function bucketStates(states: Uint8Array, maxTiles: number): Uint8Array {
  const n = states.length;
  if (n === 0) return new Uint8Array(0);
  const per = Math.max(1, Math.ceil(n / Math.max(1, maxTiles)));
  const tiles = new Uint8Array(Math.ceil(n / per));
  for (let t = 0; t < tiles.length; t++) {
    const start = t * per;
    const end = Math.min(n, start + per);
    let failed = false;
    let verified = 0;
    let touched = false;
    for (let i = start; i < end; i++) {
      const s = states[i];
      if (s === 3) failed = true;
      if (s === 2) verified++;
      if (s === 1 || s === 2) touched = true;
    }
    tiles[t] = failed ? 3 : verified === end - start ? 2 : touched ? 1 : 0;
  }
  return tiles;
}
