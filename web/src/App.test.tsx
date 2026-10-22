import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { App } from "./App";

vi.mock("./pages/Uploader", () => ({
  Uploader: ({ node }: { node: string }) => <div>uploader page: {node}</div>,
}));
vi.mock("./pages/Downloader", () => ({ Downloader: () => <div>downloader page</div> }));

const at = (path: string) =>
  render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );

afterEach(() => vi.restoreAllMocks());

describe("App routing", () => {
  it("renders the uploader at /uploader and /uploader2", () => {
    at("/uploader");
    expect(screen.getByText("uploader page: uploader")).toBeInTheDocument();
  });

  it("renders the second uploader at /uploader2", () => {
    at("/uploader2");
    expect(screen.getByText("uploader page: uploader2")).toBeInTheDocument();
  });

  it("renders the downloader at /downloader", () => {
    at("/downloader");
    expect(screen.getByText("downloader page")).toBeInTheDocument();
  });

  it("shows a not-found view with a way back", () => {
    at("/nope");
    expect(screen.getByText("That page doesn't exist.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Back to start" })).toHaveAttribute("href", "/");
  });
});

describe("Home", () => {
  it("opens each role in its own popup window", async () => {
    const open = vi.spyOn(window, "open").mockReturnValue({} as Window);
    at("/");
    await userEvent.click(screen.getByRole("link", { name: "Open the uploader window" }));
    expect(open).toHaveBeenCalledWith("/uploader", "p2p-uploader", "popup,width=720,height=900");
    await userEvent.click(screen.getByRole("link", { name: "Open the downloader window" }));
    expect(open).toHaveBeenCalledWith("/downloader", "p2p-downloader", "popup,width=720,height=900");
  });

  it("keeps plain links so a blocked popup still works", () => {
    at("/");
    expect(screen.getByRole("link", { name: "Open the uploader window" })).toHaveAttribute("href", "/uploader");
    expect(screen.getByRole("link", { name: "Open the downloader window" })).toHaveAttribute("href", "/downloader");
  });
});
