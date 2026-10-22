import { describePeerEvent, downloadReducer, initialDownload, initialServing, servingReducer } from "./reducers";
import type { DownloadEvent, PeerEvent } from "./types";

let seq = 0;
const dl = (over: Partial<DownloadEvent>): DownloadEvent => ({
  type: "download",
  seq: ++seq,
  ts: 1,
  download_id: "d1",
  kind: "chunk_ok",
  index: null,
  chunk_count: 4,
  bytes_done: 0,
  file_size: 400,
  file_name: "a.bin",
  message: null,
  ...over,
});
const peer = (over: Partial<PeerEvent>): PeerEvent => ({
  type: "peer",
  seq: ++seq,
  ts: 1,
  kind: "chunk",
  remote: "1.2.3.4:5",
  file_id: "f1",
  file_name: "a.bin",
  index: 0,
  chunk_count: 4,
  ...over,
});

describe("downloadReducer", () => {
  it("sizes the chunk array on manifest", () => {
    const s = downloadReducer(initialDownload("d1"), dl({ kind: "manifest" }));
    expect(s.states.length).toBe(4);
    expect(s.status).toBe("running");
    expect(s.fileName).toBe("a.bin");
  });

  it("marks chunks verified and tracks bytes", () => {
    let s = downloadReducer(initialDownload("d1"), dl({ kind: "manifest" }));
    s = downloadReducer(s, dl({ kind: "chunk_ok", index: 2, bytes_done: 100 }));
    expect(s.states[2]).toBe(2);
    expect(s.bytesDone).toBe(100);
  });

  it("marks a failed chunk red, then verified again after the retry", () => {
    let s = downloadReducer(initialDownload("d1"), dl({ kind: "manifest" }));
    s = downloadReducer(s, dl({ kind: "chunk_failed", index: 1, message: "bad" }));
    expect(s.states[1]).toBe(3);
    expect(s.failures).toBe(1);
    s = downloadReducer(s, dl({ kind: "chunk_ok", index: 1, bytes_done: 100 }));
    expect(s.states[1]).toBe(2);
    expect(s.failures).toBe(1);
  });

  it("ignores events it has already seen", () => {
    let s = downloadReducer(initialDownload("d1"), dl({ kind: "manifest" }));
    const ok = dl({ kind: "chunk_ok", index: 0, bytes_done: 100 });
    s = downloadReducer(s, ok);
    const again = downloadReducer(s, { ...ok, bytes_done: 999 });
    expect(again.bytesDone).toBe(100);
  });

  it("ignores events for another download", () => {
    const s = downloadReducer(initialDownload("d1"), dl({ kind: "manifest", download_id: "other" }));
    expect(s.states.length).toBe(0);
  });

  it("tracks verifying, done, error and cancelled", () => {
    let s = downloadReducer(initialDownload("d1"), dl({ kind: "manifest" }));
    s = downloadReducer(s, dl({ kind: "verifying" }));
    expect(s.status).toBe("verifying");
    expect(downloadReducer(s, dl({ kind: "done", bytes_done: 400 })).status).toBe("done");
    const err = downloadReducer(s, dl({ kind: "error", message: "boom" }));
    expect(err.status).toBe("error");
    expect(err.message).toBe("boom");
    expect(downloadReducer(s, dl({ kind: "cancelled" })).status).toBe("cancelled");
  });
});

describe("servingReducer", () => {
  it("lights served chunks per file and logs them", () => {
    const s = servingReducer(initialServing(), peer({ kind: "chunk", index: 1 }));
    expect(s.files["f1"].states[1]).toBe(2);
    expect(s.log[0].text).toContain("chunk 2 of 4");
  });

  it("marks a deliberately corrupted chunk as failed", () => {
    const s = servingReducer(initialServing(), peer({ kind: "tamper_served", index: 3 }));
    expect(s.files["f1"].states[3]).toBe(3);
  });

  it("resets a file's served chunks when a new transfer starts", () => {
    let s = servingReducer(initialServing(), peer({ kind: "chunk", index: 0 }));
    s = servingReducer(s, peer({ kind: "manifest" }));
    expect(s.files["f1"].states[0]).toBe(0);
  });

  it("counts open connections and never goes negative", () => {
    let s = servingReducer(initialServing(), peer({ kind: "connect" }));
    expect(s.connections).toBe(1);
    s = servingReducer(s, peer({ kind: "disconnect" }));
    s = servingReducer(s, peer({ kind: "disconnect" }));
    expect(s.connections).toBe(0);
  });

  it("keeps at most 200 log lines, newest first", () => {
    let s = initialServing();
    for (let i = 0; i < 250; i++) s = servingReducer(s, peer({ kind: "catalog" }));
    expect(s.log.length).toBe(200);
    expect(s.log[0].seq).toBeGreaterThan(s.log[199].seq);
  });
});

describe("describePeerEvent", () => {
  it("describes a served chunk", () => {
    expect(describePeerEvent(peer({ kind: "chunk", index: 11, chunk_count: 48, file_name: "report.pdf" }))).toBe(
      "Sent chunk 12 of 48 · report.pdf",
    );
  });

  it("describes a catalog request", () => {
    expect(describePeerEvent(peer({ kind: "catalog" }))).toBe("Someone asked for the file list");
  });
});
