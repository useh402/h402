"use client";

import { useEffect, useRef } from "react";

/** 5 by 7 pixel digits. */
const GLYPH: Record<string, string[]> = {
  "4": ["00010", "00110", "01010", "10010", "11111", "00010", "00010"],
  "0": ["01110", "10001", "10001", "10001", "10001", "10001", "01110"],
};
const TEXT = "404";
const PAD_X = 3;
const PAD_Y = 2;
export const COLS = TEXT.length * 5 + (TEXT.length - 1) + PAD_X * 2;
export const ROWS = 7 + PAD_Y * 2;

const fract = (n: number) => n - Math.floor(n);
const hash = (a: number, b: number) => fract(Math.sin(a * 12.9898 + b * 78.233) * 43758.5453);

/**
 * "404" as a matrix of pixels. The pixels assemble from left to right, a band
 * of light sweeps across them every few seconds, one flickers now and then, and
 * the ones under the cursor swell and turn blue. Unlit cells are faint dots
 * that wake up as the cursor passes. Drawn on one 2D canvas.
 */
export function Pixel404({ className }: { className?: string }) {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const canvas = ref.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    const lit = new Uint8Array(COLS * ROWS);
    [...TEXT].forEach((ch, n) => GLYPH[ch].forEach((row, r) => [...row].forEach((v, c) => {
      if (v === "1") lit[(r + PAD_Y) * COLS + PAD_X + n * 6 + c] = 1;
    })));
    const rand = Float32Array.from({ length: COLS * ROWS }, () => Math.random());

    let w = 0;
    let cell = 0;
    const resize = () => {
      const rect = canvas.getBoundingClientRect();
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = Math.max(1, Math.round(rect.width * dpr));
      canvas.height = Math.max(1, Math.round(rect.height * dpr));
      w = rect.width;
      cell = w / COLS;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();
    const observer = new ResizeObserver(resize);
    observer.observe(canvas);

    // Cursor position in cells, eased so the glow trails the mouse a little.
    const target = { x: -99, y: -99 };
    const p = { x: -99, y: -99 };
    const onMove = (e: PointerEvent) => {
      const rect = canvas.getBoundingClientRect();
      target.x = (e.clientX - rect.left) / cell;
      target.y = (e.clientY - rect.top) / cell;
    };
    window.addEventListener("pointermove", onMove);

    const square = (x: number, y: number, s: number) => {
      ctx.beginPath();
      if (ctx.roundRect) ctx.roundRect(x - s / 2, y - s / 2, s, s, s * 0.16);
      else ctx.rect(x - s / 2, y - s / 2, s, s);
      ctx.fill();
    };

    let frame = 0;
    const start = performance.now();
    const draw = (now: number) => {
      if (!reduced) frame = requestAnimationFrame(draw);
      const t = (now - start) / 1000;
      ctx.clearRect(0, 0, w, cell * ROWS);
      p.x += (target.x - p.x) * 0.14;
      p.y += (target.y - p.y) * 0.14;
      const sweep = ((t * 0.16) % 1) * 1.5 - 0.25;
      const tick = Math.floor(t * 10);

      for (let i = 0; i < lit.length; i++) {
        const c = i % COLS;
        const r = Math.floor(i / COLS);
        const a = reduced ? 1 : Math.min(1, Math.max(0, (t - (0.15 + c * 0.035 + rand[i] * 0.35)) / 0.55));
        if (a <= 0) continue;
        const e = 1 - Math.pow(1 - a, 3);
        const dx = c + 0.5 - p.x;
        const dy = r + 0.5 - p.y;
        const prox = reduced ? 0 : Math.exp(-(dx * dx + dy * dy) / 6.5);
        const phase = (c + r * 0.7) / (COLS + ROWS * 0.7);
        const shine = reduced ? 0 : Math.exp(-Math.pow(phase - sweep, 2) * 160);
        const x = (c + 0.5) * cell;
        const y = (r + 0.5) * cell;

        if (lit[i]) {
          const flicker = !reduced && hash(i, tick) > 0.992 ? 0.45 : 1;
          const glow = Math.max(prox, shine);
          const mix = Math.min(1, prox * 0.85);
          ctx.globalAlpha = e * flicker * (0.8 + 0.2 * shine) * (1 - 0.24 * ((r - PAD_Y) / 6));
          ctx.fillStyle = `rgb(${Math.round(255 - 105 * mix)},${Math.round(255 - 70 * mix)},255)`;
          ctx.shadowColor = `rgba(110,145,255,${0.22 + 0.55 * glow})`;
          ctx.shadowBlur = cell * (0.3 + 0.55 * glow);
          square(x, y, cell * 0.76 * (0.5 + 0.5 * e) * (1 + 0.16 * prox + 0.06 * shine));
        } else {
          ctx.globalAlpha = e * (0.06 + 0.32 * prox + 0.08 * shine);
          ctx.fillStyle = "rgb(170,190,255)";
          ctx.shadowBlur = 0;
          square(x, y, cell * 0.76 * (0.3 + 0.34 * prox));
        }
      }
      ctx.globalAlpha = 1;
    };
    frame = requestAnimationFrame(draw);

    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      window.removeEventListener("pointermove", onMove);
    };
  }, []);
  return <canvas ref={ref} className={className} style={{ aspectRatio: `${COLS} / ${ROWS}` }} role="img" aria-label="404" />;
}
