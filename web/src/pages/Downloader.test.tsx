import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { Downloader } from "./Downloader";
import type { CatalogEntry, DownloadEvent } from "../lib/types";

const mocks = vi.hoisted(() => ({
  api: {
    eventsUrl: "/api/downloader/events",
    peers: vi.fn(),
    peerFiles: vi.fn(),
    start: vi.fn(),
    cancel: vi.fn(),
    saved: vi.fn(),
    deleteSaved: vi.fn(),
    savedUrl: (name: string) => `/api/downloader/saved/${name}`,
  },
  handler: { current: null as null | ((e: unknown) => void) },
}));

vi.mock("../lib/api", async (original) => ({
  ...(await original<typeof import("../lib/api")>()),
  downloaderApi: () => mocks.api,
}));
vi.mock("../lib/useEventStream", () => ({
  useEventStream: (_url: string, cb: (e: unknown) => void) => {
    mocks.handler.current = cb;
    return "open";
  },
}));

const entry: CatalogEntry = {
  file_id: "f1",
  file_name: "a.bin",
  file_size: 400,
  chunk_size: 100,
  file_hash: "deadbeefcafe",
  chunk_count: 4,
  aliases: [],
};

const peers = [
  { label: "Uploader", host: "uploader", port: 9000, reachable: true, file_count: 1 },
  { label: "Uploader 2", host: "uploader2", port: 9000, reachable: true, file_count: 0 },
];

let seq = 0;
const dl = (over: Partial<DownloadEvent>): DownloadEvent => ({
  type: "download",
  seq: ++seq,
  ts: 10,
  download_id: "d1",
  kind: "manifest",
  index: null,
  chunk_count: 4,
  bytes_done: 0,
  file_size: 400,
  file_name: "a.bin",
  message: null,
  ...over,
});
const push = (e: DownloadEvent) => act(() => mocks.handler.current!(e));

function renderPage() {
  return render(
    <MemoryRouter>
      <Downloader />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.api.peers.mockResolvedValue(peers);
  mocks.api.peerFiles.mockResolvedValue([entry]);
  mocks.api.saved.mockResolvedValue([]);
  mocks.api.start.mockResolvedValue({ download_id: "d1", file_name: "a.bin" });
  mocks.api.cancel.mockResolvedValue({});
});

async function startDownload() {
  await userEvent.click(await screen.findByRole("button", { name: "Download a.bin" }));
  await waitFor(() => expect(mocks.api.start).toHaveBeenCalled());
}

describe("Downloader page", () => {
  it("connects to the first reachable peer and lists its files", async () => {
    renderPage();
    expect(await screen.findByText("a.bin")).toBeInTheDocument();
    expect(mocks.api.peerFiles).toHaveBeenCalledWith("Uploader");
  });

  it("starts a download with the chosen speed and connections", async () => {
    renderPage();
    fireEvent.change(await screen.findByLabelText(/Demo speed/), { target: { value: "80" } });
    await startDownload();
    expect(mocks.api.start).toHaveBeenCalledWith({
      peer: "Uploader",
      file_id: "f1",
      connections: 4,
      chunk_delay_ms: 80,
    });
  });

  it("counts a failed hash check, then shows the chunk verified after the retry", async () => {
    renderPage();
    await startDownload();
    push(dl({ kind: "manifest" }));
    push(dl({ kind: "chunk_failed", index: 1, message: "Chunk 2 failed its hash check (attempt 1 of 4)" }));
    const failed = await screen.findByText("Failed hash checks");
    expect(failed.parentElement).toHaveTextContent("1");
    expect(screen.getByRole("img", { name: "a.bin: 0 of 4 chunks verified" })).toBeInTheDocument();
    expect(screen.getByText("Chunk 2 failed its hash check (attempt 1 of 4)")).toBeInTheDocument();
    push(dl({ kind: "chunk_ok", index: 1, bytes_done: 100 }));
    expect(await screen.findByRole("img", { name: "a.bin: 1 of 4 chunks verified" })).toBeInTheDocument();
  });

  it("shows the verified verdict with the file hash when the download is done", async () => {
    renderPage();
    await startDownload();
    push(dl({ kind: "manifest" }));
    push(dl({ kind: "verifying" }));
    expect(await screen.findByText("Checking the whole file…")).toBeInTheDocument();
    push(dl({ kind: "done", bytes_done: 400 }));
    expect(await screen.findByText("Downloaded and verified")).toBeInTheDocument();
    expect(screen.getByText(/deadbeefcafe/)).toBeInTheDocument();
  });

  it("cancels a running download", async () => {
    renderPage();
    await startDownload();
    push(dl({ kind: "manifest" }));
    await userEvent.click(await screen.findByRole("button", { name: "Cancel a.bin" }));
    expect(mocks.api.cancel).toHaveBeenCalledWith("d1");
  });

  it("explains an unreachable peer", async () => {
    const { ApiError } = await import("../lib/api");
    mocks.api.peerFiles.mockRejectedValue(new ApiError("Can't reach uploader:9000. Check that the peer is running.", 502));
    renderPage();
    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText(/Can't reach uploader:9000/)).toBeInTheDocument();
  });

  it("offers a saved file for download to this computer", async () => {
    mocks.api.saved.mockResolvedValue([{ name: "a.bin", size: 400 }]);
    renderPage();
    const link = await screen.findByRole("link", { name: /Save a.bin to this computer/ });
    expect(link).toHaveAttribute("href", "/api/downloader/saved/a.bin");
  });
});
