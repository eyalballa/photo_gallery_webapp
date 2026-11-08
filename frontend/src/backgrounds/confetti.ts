import { pick, rand } from "../lib/random";
import { canvasBackground } from "./canvas";

interface Piece { x: number; y: number; w: number; h: number; rot: number; vr: number; vy: number; ph: number; c: string }

export const confetti = canvasBackground<Piece[]>({
  id: "confetti",
  label: "Confetti",
  swatch: "linear-gradient(135deg,#ff5d73,#ffc145 50%,#4cc9f0)",
  themes: ["kids", "grown", "roses"],
  setup(w, h, { palette }) {
    return Array.from({ length: 150 }, () => ({
      x: rand(0, w), y: rand(-h, h), w: rand(6, 12), h: rand(10, 18),
      rot: rand(0, 6.28), vr: rand(-2, 2), vy: rand(30, 70), ph: rand(0, 6.28), c: pick(palette),
    }));
  },
  frame(ctx, ps, w, h, t, dt) {
    const g = ctx.createLinearGradient(0, 0, 0, h);
    g.addColorStop(0, "#2b1055");
    g.addColorStop(1, "#130a2c");
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, w, h);
    ctx.globalAlpha = 0.7;
    for (const p of ps) {
      p.y += p.vy * dt;
      p.x += Math.sin(t + p.ph) * 25 * dt;
      p.rot += p.vr * dt;
      if (p.y > h + 20) { p.y = -20; p.x = rand(0, w); }
      ctx.save();
      ctx.translate(p.x, p.y);
      ctx.rotate(p.rot);
      ctx.scale(1, Math.cos(t * 2 + p.ph));
      ctx.fillStyle = p.c;
      ctx.fillRect(-p.w / 2, -p.h / 2, p.w, p.h);
      ctx.restore();
    }
    ctx.globalAlpha = 1;
  },
});
