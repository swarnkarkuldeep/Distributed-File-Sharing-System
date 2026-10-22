import { render } from "@testing-library/react";
import { Mosaic } from "./Mosaic";

describe("Mosaic width tracking", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("starts observing its container once chunks arrive after an empty first render", () => {
    const observe = vi.fn();
    class FakeResizeObserver {
      observe = observe;
      disconnect = vi.fn();
      constructor(_cb: unknown) {}
    }
    vi.stubGlobal("ResizeObserver", FakeResizeObserver);

    const { rerender } = render(<Mosaic states={new Uint8Array(0)} />);
    expect(observe).not.toHaveBeenCalled();
    rerender(<Mosaic states={new Uint8Array(10)} />);
    expect(observe).toHaveBeenCalledTimes(1);
  });
});
