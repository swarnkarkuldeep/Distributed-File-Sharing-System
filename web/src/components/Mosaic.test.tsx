import { render, screen } from "@testing-library/react";
import { Mosaic } from "./Mosaic";

function states(total: number, verified: number): Uint8Array {
  const s = new Uint8Array(total);
  s.fill(2, 0, verified);
  return s;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("Mosaic", () => {
  it("renders a canvas whose label summarises verified chunks", () => {
    render(<Mosaic states={states(48, 32)} />);
    const canvas = screen.getByRole("img");
    expect(canvas.tagName).toBe("CANVAS");
    expect(canvas).toHaveAccessibleName("32 of 48 chunks verified");
  });

  it("prefixes the label when one is given", () => {
    render(<Mosaic states={states(10, 10)} label="movie.mkv" />);
    expect(screen.getByRole("img")).toHaveAccessibleName("movie.mkv: 10 of 10 chunks verified");
  });

  it("falls back to a progress bar under reduced motion", () => {
    vi.stubGlobal("matchMedia", (query: string) => ({
      matches: query.includes("prefers-reduced-motion"),
      media: query,
      addEventListener: () => {},
      removeEventListener: () => {},
    }));
    render(<Mosaic states={states(48, 32)} />);
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
    const bar = screen.getByRole("progressbar");
    expect(bar).toHaveAttribute("aria-valuenow", "32");
    expect(bar).toHaveAttribute("aria-valuemax", "48");
  });

  it("shows the empty text when there are no chunks yet", () => {
    render(<Mosaic states={new Uint8Array(0)} emptyText="Chunks appear here once a transfer starts." />);
    expect(screen.getByText("Chunks appear here once a transfer starts.")).toBeInTheDocument();
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
  });
});
