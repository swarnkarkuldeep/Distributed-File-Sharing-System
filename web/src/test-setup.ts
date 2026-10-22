import "@testing-library/jest-dom/vitest";

// jsdom has no canvas; the Mosaic copes with a null context.
HTMLCanvasElement.prototype.getContext = (() => null) as unknown as typeof HTMLCanvasElement.prototype.getContext;
