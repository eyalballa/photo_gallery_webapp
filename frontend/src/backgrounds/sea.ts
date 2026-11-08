import { rand } from "../lib/random";
import { canvasBackground } from "./canvas";

interface Bubble { x: number; y: number; r: number; vy: number; ph: number }

export const sea = canvasBackground<Bubble[]>({
  id: "sea",
  label: "Under the sea",
  swatch: "linear-gradient(180deg,#1680a8,#04263a)",
  themes: ["kids"],
  setup(w, h) {
    return Array.from({ length: 70 }, () => ({ x: rand(0, w), y: rand(0, h), r: rand(3, 14), vy: rand(15, 45), ph: rand(0, 6.28) }));
  },
  frame(ctx, bubbles, w, h, t, dt) {
    const g = ctx.createLinearGradient(0, 0, 0, h);
    g.addColorStop(0, "#0e5f80");
    g.addColorStop(1, "#03202f");
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, w, h);
    ctx.fillStyle = "rgba(180,240,255,0.05)";
    for (let i = 0; i < 6; i++) {
      const x = (w * (i + 0.5)) / 6 + Math.sin(t * 0.3 + i) * 40;
      ctx.beginPath();
      ctx.moveTo(x - 30, 0);
      ctx.lineTo(x + 30, 0);
      ctx.lineTo(x + 160, h);
      ctx.lineTo(x - 60, h);
      ctx.fill();
    }
    ctx.lineWidth = 1.5;
    for (const b of bubbles) {
      b.y -= b.vy * dt;
      b.x += Math.sin(t * 1.5 + b.ph) * 12 * dt;
      if (b.y < -b.r) { b.y = h + b.r; b.x = rand(0, w); }
      ctx.strokeStyle = "rgba(255,255,255,0.35)";
      ctx.beginPath();
      ctx.arc(b.x, b.y, b.r, 0, 6.283);
      ctx.stroke();
      ctx.fillStyle = "rgba(255,255,255,0.4)";
      ctx.beginPath();
      ctx.arc(b.x - b.r * 0.35, b.y - b.r * 0.35, b.r * 0.22, 0, 6.283);
      ctx.fill();
    }
  },
});
