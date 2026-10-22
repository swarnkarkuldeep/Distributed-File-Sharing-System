import { formatBytes } from "./format";

describe("formatBytes", () => {
  it("handles zero and small values", () => {
    expect(formatBytes(0)).toBe("0 B");
    expect(formatBytes(512)).toBe("512 B");
  });

  it("scales units with one decimal under 10", () => {
    expect(formatBytes(1536)).toBe("1.5 KB");
    expect(formatBytes(1048576)).toBe("1 MB");
    expect(formatBytes(25 * 1024 * 1024)).toBe("25 MB");
  });
});
