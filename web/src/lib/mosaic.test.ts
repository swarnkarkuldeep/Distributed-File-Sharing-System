import { bucketStates } from "./mosaic";

const u = (...n: number[]) => Uint8Array.from(n);

describe("bucketStates", () => {
  it("returns a copy when chunks fit in the tile budget", () => {
    const input = u(0, 2, 3);
    const out = bucketStates(input, 10);
    expect(Array.from(out)).toEqual([0, 2, 3]);
    expect(out).not.toBe(input);
  });

  it("returns an empty array for no chunks", () => {
    expect(bucketStates(new Uint8Array(0), 10).length).toBe(0);
  });

  it("marks a tile failed if any member failed", () => {
    expect(Array.from(bucketStates(u(2, 3, 2, 2), 2))).toEqual([3, 2]);
  });

  it("marks a tile verified only when every member is verified", () => {
    expect(Array.from(bucketStates(u(2, 2, 2, 0), 2))).toEqual([2, 1]);
  });

  it("marks a tile active when any member is active", () => {
    expect(Array.from(bucketStates(u(0, 1, 0, 0), 2))).toEqual([1, 0]);
  });

  it("never exceeds maxTiles", () => {
    expect(bucketStates(new Uint8Array(4800), 400).length).toBeLessThanOrEqual(400);
    expect(bucketStates(new Uint8Array(401), 400).length).toBeLessThanOrEqual(400);
  });
});
