import { hexToRgb, pick, rand } from "../lib/random";
import { canvasBackground } from "./canvas";

interface Dot { x: number; y: number; r: number; c: string; a: number; vx: number; vy: number; ph: number }

export const partyNight = canvasBackground<Dot[]>({
  id: "party-night",
  label: "Party night",
  swatch: "linear-gradient(135deg,#1b2160,#0e1230)",
  themes: ["kids"],
  setup(w, h, { palette }) {
    const rgb = palette.map(hexToRgb);
    return Array.from({ length: 46 }, () => ({
      x: rand(0, w), y: rand(0, h), r: rand(24, 130), c: pick(rgb), a: rand(0.06, 0.16),
      vx: rand(-6, 6), vy: rand(-10, -2), ph: rand(0, 6.28),
    }));
  },
  frame(ctx, dots, w, h, t, dt) {
    const g = ctx.createRadialGradient(w * 0.5, h * 0.1, 0, w * 0.5, h * 0.4, Math.max(w, h));
    g.addColorStop(0, "#252c70");
    g.addColorStop(1, "#0b0e26");
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, w, h);
    ctx.globalCompositeOperation = "lighter";
    for (const d of dots) {
      d.x += d.vx * dt;
      d.y += d.vy * dt;
      if (d.y < -d.r) { d.y = h + d.r; d.x = rand(0, w); }
      if (d.x < -d.r) d.x = w + d.r;
      else if (d.x > w + d.r) d.x = -d.r;
      const a = d.a * (0.6 + 0.4 * Math.sin(t * 0.7 + d.ph));
      const rg = ctx.createRadialGradient(d.x, d.y, 0, d.x, d.y, d.r);
      rg.addColorStop(0, `rgba(${d.c},${a})`);
      rg.addColorStop(0.7, `rgba(${d.c},${a * 0.6})`);
      rg.addColorStop(1, `rgba(${d.c},0)`);
      ctx.fillStyle = rg;
      ctx.beginPath();
      ctx.arc(d.x, d.y, d.r, 0, 6.283);
      ctx.fill();
    }
    ctx.globalCompositeOperation = "source-over";
  },
});
