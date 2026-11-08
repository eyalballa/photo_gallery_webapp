import type { Background, BackgroundContext } from "../types";

export interface CanvasSpec<S> {
  id: string;
  label: string;
  swatch: string;
  themes: string[];
  setup(w: number, h: number, ctx: BackgroundContext): S;
  /** t: seconds since page load; dt: seconds since the last frame (capped, slowed under reduced motion). */
  frame(c: CanvasRenderingContext2D, state: S, w: number, h: number, t: number, dt: number): void;
}

const MAX_DPR = 1.5;

/** A full-screen animated canvas background; resizes with the window and stops on unmount. */
export function canvasBackground<S>(spec: CanvasSpec<S>): Background {
  return {
    id: spec.id,
    label: spec.label,
    swatch: spec.swatch,
    themes: spec.themes,
    mount(host, bgCtx) {
      const canvas = document.createElement("canvas");
      host.appendChild(canvas);
      const c = canvas.getContext("2d");
      if (!c) return () => canvas.remove();
      let state: S;
      const onResize = () => {
        const d = Math.min(window.devicePixelRatio || 1, MAX_DPR);
        canvas.width = host.clientWidth * d;
        canvas.height = host.clientHeight * d;
        c.setTransform(d, 0, 0, d, 0, 0);
        state = spec.setup(host.clientWidth, host.clientHeight, bgCtx);
      };
      onResize();
      window.addEventListener("resize", onResize);
      let last = performance.now();
      let raf = 0;
      const loop = (t: number) => {
        const dt = Math.min((t - last) / 1000, 0.05) * (bgCtx.reducedMotion ? 0.15 : 1);
        last = t;
        spec.frame(c, state, host.clientWidth, host.clientHeight, t / 1000, dt);
        raf = requestAnimationFrame(loop);
      };
      raf = requestAnimationFrame(loop);
      return () => {
        cancelAnimationFrame(raf);
        window.removeEventListener("resize", onResize);
        canvas.remove();
      };
    },
  };
}
