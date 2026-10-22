import { useEffect, useMemo, useRef, useState } from "react";
import { bucketStates } from "../lib/mosaic";
import { ProgressBar } from "./ProgressBar";

const TILE = 16;
const GAP = 4;
const ANIMATION_MS = 450;
const FALLBACK_GLOW = "#8F7CFF";
const DANGER = "#FF5C7A";

function usePrefersReducedMotion(): boolean {
  const query = "(prefers-reduced-motion: reduce)";
  const read = () => typeof window.matchMedia === "function" && window.matchMedia(query).matches;
  const [reduced, setReduced] = useState(read);
  useEffect(() => {
    if (typeof window.matchMedia !== "function") return;
    const list = window.matchMedia(query);
    const onChange = () => setReduced(list.matches);
    list.addEventListener?.("change", onChange);
    return () => list.removeEventListener?.("change", onChange);
  }, []);
  return reduced;
}

function useWidth(ref: React.RefObject<HTMLElement | null>): number {
  const [width, setWidth] = useState(640);
  useEffect(() => {
    const el = ref.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(([entry]) => setWidth(Math.max(120, Math.floor(entry.contentRect.width))));
    observer.observe(el);
    return () => observer.disconnect();
  }, [ref]);
  return width;
}

function roundedRect(ctx: CanvasRenderingContext2D, x: number, y: number, size: number, radius: number) {
  ctx.beginPath();
  if (typeof ctx.roundRect === "function") ctx.roundRect(x, y, size, size, radius);
  else ctx.rect(x, y, size, size);
}

interface Props {
  /** Per-chunk state: 0 pending, 1 active, 2 verified, 3 failed. */
  states: Uint8Array;
  label?: string;
  maxTiles?: number;
  emptyText?: string;
}

/** Every chunk as a tile. Lit tiles are chunks whose SHA-256 has been checked. */
export function Mosaic({ states, label, maxTiles = 400, emptyText = "Chunks appear here once a transfer starts." }: Props) {
  const reduced = usePrefersReducedMotion();
  const wrapRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const width = useWidth(wrapRef);
  const previous = useRef<Uint8Array>(new Uint8Array(0));
  const changedAt = useRef<number[]>([]);

  const verified = useMemo(() => states.reduce((n, s) => n + (s === 2 ? 1 : 0), 0), [states]);
  const tiles = useMemo(() => bucketStates(states, maxTiles), [states, maxTiles]);
  const summary = `${verified} of ${states.length} chunks verified`;
  const accessibleName = label ? `${label}: ${summary}` : summary;
  const showCanvas = !reduced && states.length > 0;

  useEffect(() => {
    if (!showCanvas) return;
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;

    const now = performance.now();
    const prev = previous.current;
    const sameShape = prev.length === tiles.length;
    changedAt.current = Array.from(tiles, (s, i) =>
      sameShape && prev[i] !== s ? now : (changedAt.current[i] ?? -Infinity),
    );
    previous.current = tiles;

    const cols = Math.max(1, Math.floor((width + GAP) / (TILE + GAP)));
    const rows = Math.ceil(tiles.length / cols);
    const cssHeight = rows * (TILE + GAP) - GAP;
    const dpr = window.devicePixelRatio || 1;
    canvas.width = Math.floor(width * dpr);
    canvas.height = Math.floor(cssHeight * dpr);
    canvas.style.width = `${width}px`;
    canvas.style.height = `${cssHeight}px`;
    const glow = getComputedStyle(canvas).getPropertyValue("--glow").trim() || FALLBACK_GLOW;

    let raf = 0;
    const draw = (time: number) => {
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, width, cssHeight);
      let animating = false;
      for (let i = 0; i < tiles.length; i++) {
        const state = tiles[i];
        const age = time - changedAt.current[i];
        const t = Math.min(1, Math.max(0, age / ANIMATION_MS));
        if (t < 1) animating = true;
        let x = (i % cols) * (TILE + GAP);
        const y = Math.floor(i / cols) * (TILE + GAP);
        let size = TILE;
        ctx.shadowBlur = 0;
        ctx.globalAlpha = 1;

        if (state === 0) {
          ctx.fillStyle = "rgba(255,255,255,0.09)";
        } else if (state === 1) {
          animating = true;
          ctx.fillStyle = glow;
          ctx.globalAlpha = 0.35 + 0.25 * Math.sin(time / 160 + i);
        } else if (state === 2) {
          ctx.fillStyle = glow;
          if (t < 1) {
            const pop = 1 + 0.4 * (1 - t) * (1 - t);
            size = TILE * pop;
            x -= (size - TILE) / 2;
            ctx.shadowColor = glow;
            ctx.shadowBlur = 14 * (1 - t);
          }
        } else {
          ctx.fillStyle = DANGER;
          if (t < 1) x += Math.sin(age / 26) * 3 * (1 - t);
        }
        roundedRect(ctx, x, y - (size - TILE) / 2, size, 4);
        ctx.fill();
      }
      ctx.globalAlpha = 1;
      ctx.shadowBlur = 0;
      if (animating) raf = requestAnimationFrame(draw);
    };
    raf = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(raf);
  }, [tiles, width, showCanvas]);

  if (states.length === 0) {
    return <div className="mosaic-empty">{emptyText}</div>;
  }
  if (reduced) {
    return <ProgressBar value={verified} max={states.length} label={accessibleName} />;
  }
  return (
    <div ref={wrapRef} className="mosaic">
      <canvas ref={canvasRef} role="img" aria-label={accessibleName} />
    </div>
  );
}
