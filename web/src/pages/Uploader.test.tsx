import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { Uploader } from "./Uploader";
import type { CatalogEntry, PeerEvent } from "../lib/types";

const mocks = vi.hoisted(() => ({
  api: {
    eventsUrl: "/api/uploader/events",
    status: vi.fn(),
    files: vi.fn(),
    upload: vi.fn(),
    remove: vi.fn(),
    arm: vi.fn(),
    disarm: vi.fn(),
  },
  handler: { current: null as null | ((e: unknown) => void) },
}));

vi.mock("../lib/api", async (original) => ({
  ...(await original<typeof import("../lib/api")>()),
  uploaderApi: () => mocks.api,
}));
vi.mock("../lib/useEventStream", () => ({
  useEventStream: (_url: string, cb: (e: unknown) => void) => {
    mocks.handler.current = cb;
    return "open";
  },
}));

const entry = (over: Partial<CatalogEntry> = {}): CatalogEntry => ({
  file_id: "f1",
  file_name: "a.bin",
  file_size: 5000,
  chunk_size: 1000,
  file_hash: "abc",
  chunk_count: 5,
  aliases: [],
  ...over,
});

const status = { role: "uploader", peer_port: 9000, chunk_size: 1000, file_count: 0, tamper: null };

function renderPage() {
  return render(
    <MemoryRouter>
      <Uploader node="uploader" />
    </MemoryRouter>,
  );
}

let seq = 0;
const peerEvent = (over: Partial<PeerEvent>): PeerEvent => ({
  type: "peer",
  seq: ++seq,
  ts: 1,
  kind: "chunk",
  remote: "1.2.3.4:5",
  file_id: "f1",
  file_name: "a.bin",
  index: 0,
  chunk_count: 5,
  ...over,
});

beforeEach(() => {
  vi.clearAllMocks();
  mocks.api.status.mockResolvedValue(status);
  mocks.api.files.mockResolvedValue([]);
});

describe("Uploader page", () => {
  it("invites the user to drop a file when nothing is shared", async () => {
    renderPage();
    expect(await screen.findByText("Drop a file here to start sharing it.")).toBeInTheDocument();
  });

  it("uploads a dropped file and lists it as shared", async () => {
    mocks.api.upload.mockResolvedValue(entry());
    renderPage();
    const file = new File(["hello"], "a.bin");
    await userEvent.upload(await screen.findByLabelText("Choose files to share"), file);
    expect(mocks.api.upload).toHaveBeenCalledWith(file, expect.any(Function));
    expect(await screen.findByText("a.bin")).toBeInTheDocument();
  });

  it("names the file when an upload fails", async () => {
    const { ApiError } = await import("../lib/api");
    mocks.api.upload.mockRejectedValue(new ApiError("big.bin: larger than 512 MB", 413));
    renderPage();
    await userEvent.upload(await screen.findByLabelText("Choose files to share"), new File(["x"], "big.bin"));
    expect(await screen.findByText("big.bin: larger than 512 MB")).toBeInTheDocument();
  });

  it("lights a tile when the peer serves a chunk", async () => {
    mocks.api.files.mockResolvedValue([entry()]);
    renderPage();
    expect(await screen.findByRole("img", { name: "a.bin: 0 of 5 chunks verified" })).toBeInTheDocument();
    act(() => mocks.handler.current!(peerEvent({ index: 1 })));
    expect(await screen.findByRole("img", { name: "a.bin: 1 of 5 chunks verified" })).toBeInTheDocument();
    expect(screen.getByText("Sent chunk 2 of 5 · a.bin")).toBeInTheDocument();
  });

  it("arms the tamper control for the chosen chunk", async () => {
    mocks.api.files.mockResolvedValue([entry()]);
    mocks.api.arm.mockResolvedValue({ file_id: "f1", index: 2, once: true });
    renderPage();
    const button = await screen.findByRole("button", { name: "Corrupt this chunk once" });
    await userEvent.click(button);
    await waitFor(() => expect(mocks.api.arm).toHaveBeenCalledWith({ file_id: "f1", index: 2, once: true }));
  });

  it("removes a file", async () => {
    mocks.api.files.mockResolvedValue([entry()]);
    mocks.api.remove.mockResolvedValue(undefined);
    renderPage();
    await userEvent.click(await screen.findByRole("button", { name: "Stop sharing a.bin" }));
    await waitFor(() => expect(mocks.api.remove).toHaveBeenCalledWith("f1"));
    expect(await screen.findByText("Drop a file here to start sharing it.")).toBeInTheDocument();
  });
});
