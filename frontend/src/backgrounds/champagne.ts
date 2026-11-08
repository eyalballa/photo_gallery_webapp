import { rand } from "../lib/random";
import { canvasBackground } from "./canvas";

interface Fizz { x: number; y: number; r: number; vy: number; ph: number }

export const champagne = canvasBackground<Fizz[]>({
  id: "champagne",
  label: "Champagne",
  swatch: "radial-gradient(circle at 50% 80%,#e3c193,#17101c 60%)",
  themes: ["grown"],
  setup(w, h) {
    return Array.from({ length: 110 }, () => ({ x: rand(0, w), y: rand(0, h), r: rand(0.8, 2.4), vy: rand(6, 20), ph: rand(0, 6.28) }));
  },
  frame(ctx, ps, w, h, t, dt) {
    const g = ctx.createLinearGradient(0, 0, 0, h);
    g.addColorStop(0, "#0c080f");
    g.addColorStop(1, "#21151d");
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, w, h);
    const glow = ctx.createRadialGradient(w / 2, h * 1.1, 0, w / 2, h * 1.1, h * 0.9);
    glow.addColorStop(0, "rgba(227,193,147,.16)");
    glow.addColorStop(1, "rgba(227,193,147,0)");
    ctx.fillStyle = glow;
    ctx.fillRect(0, 0, w, h);
    for (const p of ps) {
      p.y -= p.vy * dt;
      p.x += Math.sin(t * 0.6 + p.ph) * 4 * dt;
      if (p.y < -4) { p.y = h + 4; p.x = rand(0, w); }
      ctx.fillStyle = `rgba(232,201,160,${0.25 + 0.45 * Math.abs(Math.sin(t * 0.9 + p.ph))})`;
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.r, 0, 6.283);
      ctx.fill();
    }
  },
});
