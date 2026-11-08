import { rand } from "../lib/random";
import { canvasBackground } from "./canvas";

interface Blob { c: string; ph: number; r: number; ax: number; ay: number; cx: number; cy: number }

const COLORS = ["110,46,102", "168,84,106", "44,47,107", "138,90,43", "80,40,120"];

export const velvet = canvasBackground<Blob[]>({
  id: "velvet",
  label: "Velvet",
  swatch: "radial-gradient(circle at 30% 30%,#a8546a,#2c2f6b 55%,#120c16)",
  themes: ["grown"],
  setup(w, h) {
    return COLORS.map((c, i) => ({
      c, ph: i * 1.3, r: Math.max(w, h) * rand(0.35, 0.55),
      ax: rand(0.15, 0.35), ay: rand(0.1, 0.3), cx: rand(0.2, 0.8), cy: rand(0.2, 0.8),
    }));
  },
  frame(ctx, blobs, w, h, t) {
    ctx.fillStyle = "#120c16";
    ctx.fillRect(0, 0, w, h);
    for (const b of blobs) {
      const x = w * (b.cx + Math.sin(t * 0.04 + b.ph) * b.ax);
      const y = h * (b.cy + Math.cos(t * 0.05 + b.ph) * b.ay);
      const g = ctx.createRadialGradient(x, y, 0, x, y, b.r);
      g.addColorStop(0, `rgba(${b.c},0.42)`);
      g.addColorStop(1, `rgba(${b.c},0)`);
      ctx.fillStyle = g;
      ctx.fillRect(0, 0, w, h);
    }
  },
});
