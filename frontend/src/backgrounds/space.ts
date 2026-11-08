import { rand } from "../lib/random";
import { canvasBackground } from "./canvas";

interface Star { x: number; y: number; s: number; ph: number }
interface Shoot { x: number; y: number; life: number }
interface SpaceState { stars: Star[]; planet: { x: number; y: number; r: number }; shoot: Shoot | null; nextShoot: number }

export const space = canvasBackground<SpaceState>({
  id: "space",
  label: "Outer space",
  swatch: "radial-gradient(circle at 70% 30%,#b388ff,#0d0b2e 60%)",
  themes: ["kids"],
  setup(w, h) {
    return {
      stars: Array.from({ length: 280 }, () => ({ x: rand(0, w), y: rand(0, h), s: rand(0.5, 2), ph: rand(0, 6.28) })),
      planet: { x: w * 0.12, y: h * 0.85, r: Math.min(w, h) * 0.22 },
      shoot: null,
      nextShoot: 4,
    };
  },
  frame(ctx, st, w, h, t, dt) {
    const g = ctx.createLinearGradient(0, 0, w, h);
    g.addColorStop(0, "#05061a");
    g.addColorStop(1, "#140f3d");
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, w, h);
    ctx.fillStyle = "#fff";
    for (const s of st.stars) {
      ctx.globalAlpha = 0.45 + 0.55 * Math.abs(Math.sin(t * 0.8 + s.ph));
      ctx.fillRect(s.x, s.y, s.s, s.s);
    }
    ctx.globalAlpha = 1;
    const p = st.planet;
    p.x += 3 * dt;
    if (p.x - p.r * 1.8 > w) p.x = -p.r * 1.8;
    const pg = ctx.createRadialGradient(p.x - p.r * 0.4, p.y - p.r * 0.4, p.r * 0.1, p.x, p.y, p.r);
    pg.addColorStop(0, "#c9a7ff");
    pg.addColorStop(1, "#4b2a8a");
    ctx.fillStyle = pg;
    ctx.beginPath();
    ctx.arc(p.x, p.y, p.r, 0, 6.283);
    ctx.fill();
    ctx.strokeStyle = "rgba(255,193,69,.55)";
    ctx.lineWidth = p.r * 0.07;
    ctx.beginPath();
    ctx.ellipse(p.x, p.y, p.r * 1.7, p.r * 0.38, -0.25, 0, 6.283);
    ctx.stroke();
    st.nextShoot -= dt;
    if (!st.shoot && st.nextShoot <= 0) st.shoot = { x: rand(w * 0.4, w), y: rand(0, h * 0.4), life: 1 };
    const s = st.shoot;
    if (s) {
      s.x -= 700 * dt;
      s.y += 260 * dt;
      s.life -= dt * 1.2;
      const lg = ctx.createLinearGradient(s.x, s.y, s.x + 140, s.y - 52);
      lg.addColorStop(0, `rgba(255,255,255,${Math.max(s.life, 0)})`);
      lg.addColorStop(1, "rgba(255,255,255,0)");
      ctx.strokeStyle = lg;
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(s.x, s.y);
      ctx.lineTo(s.x + 140, s.y - 52);
      ctx.stroke();
      if (s.life <= 0) { st.shoot = null; st.nextShoot = rand(5, 10); }
    }
  },
});
