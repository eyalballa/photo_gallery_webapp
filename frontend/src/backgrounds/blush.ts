import { rand } from "../lib/random";
import { canvasBackground } from "./canvas";

interface Wash { c: string; ph: number; r: number; ax: number; ay: number; cx: number; cy: number }
interface Frame { pts: { a: number; k: number }[]; ph: number }
interface Cluster { img: HTMLImageElement; x: number; y: number; size: number }
interface State { washes: Wash[]; frames: Frame[]; clusters: Cluster[]; paper: CanvasPattern | null }

const WASHES = ["247,201,190", "250,224,214", "243,190,206", "255,236,226", "238,206,196"];

/** An arc around (ox, oy) from angle a0 to a1 (degrees) at radius r, as an SVG path. */
function arc(ox: number, oy: number, r: number, a0: number, a1: number): string {
  const p = (a: number) =>
    `${(ox + Math.cos((a * Math.PI) / 180) * r).toFixed(1)} ${(oy + Math.sin((a * Math.PI) / 180) * r).toFixed(1)}`;
  return `M${p(a0)} A${r} ${r} 0 ${a1 - a0 > 180 ? 1 : 0} 1 ${p(a1)}`;
}

/** One watercolor rose, painted like the invitation's: a scalloped pink bloom with white gaps between
 *  overlapping petals, each petal curve off-centre and turned on (golden angle), darker towards the heart. */
function rose(cx: number, cy: number, r: number, shade: string): string {
  const turn = rand(0, 360);
  const scallops = Array.from({ length: 6 }, (_, i) => {
    const a = ((turn + i * 60) * Math.PI) / 180;
    return `<circle cx="${(Math.cos(a) * r * 0.34).toFixed(1)}" cy="${(Math.sin(a) * r * 0.34).toFixed(1)}" r="${r * 0.68}" fill="${shade}" opacity=".55"/>`;
  }).join("");
  const gaps = [0.8, 0.66, 0.52, 0.4, 0.28].map((k, i) => {
    const a0 = turn + i * 137.5;
    const off = r * 0.1;
    return `<path d="${arc(rand(-off, off), rand(-off, off), r * k, a0, a0 + rand(110, 160))}" fill="none" stroke="#fff"
      stroke-width="${r * (0.09 - i * 0.008)}" stroke-linecap="round" opacity=".8"/>`;
  }).join("");
  return `<g transform="translate(${cx} ${cy})">${scallops}
    <circle r="${r * 0.5}" fill="#e2639f" opacity=".3"/>
    <circle cx="${r * 0.04}" cy="${-r * 0.03}" r="${r * 0.2}" fill="#cf4f8c" opacity=".45"/>${gaps}
  </g>`;
}

function leaf(x: number, y: number, len: number, angle: number): string {
  return `<path d="M0 0 q${len * 0.35} ${-len * 0.28} ${len} 0 q${-len * 0.65} ${len * 0.28} ${-len} 0z" fill="#9fb487" opacity=".8"
    transform="translate(${x} ${y}) rotate(${angle})"/>`;
}

/** Three roses, leaves and a few dots, like the invitation's corner bouquets. */
function clusterSvg(): string {
  const leaves = [leaf(22, 60, 34, 200), leaf(150, 40, 30, -30), leaf(120, 150, 32, 40), leaf(40, 140, 28, 150), leaf(95, 18, 26, -80)].join("");
  const dots = Array.from({ length: 6 }, () => `<circle cx="${rand(10, 170)}" cy="${rand(10, 170)}" r="${rand(1.5, 3)}" fill="#ec7ab3" opacity=".6"/>`).join("");
  const body = leaves + rose(70, 95, 46, "#ef8fbd") + rose(128, 62, 32, "#f3a2c6") + rose(118, 128, 26, "#f6b1cf") + dots;
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 180 180" width="360" height="360">${body}</svg>`;
}

function clusterImage(): HTMLImageElement {
  const img = new Image();
  img.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(clusterSvg())}`;
  return img;
}

/** A faint paper grain, drawn once and tiled. */
function paperPattern(ctx: CanvasRenderingContext2D): CanvasPattern | null {
  const c = document.createElement("canvas");
  c.width = c.height = 160;
  const g = c.getContext("2d");
  if (!g) return null;
  for (let i = 0; i < 1400; i++) {
    g.fillStyle = `rgba(${Math.random() < 0.5 ? "255,255,255" : "160,110,110"},${rand(0.03, 0.08)})`;
    g.fillRect(rand(0, 160), rand(0, 160), 1, 1);
  }
  return ctx.createPattern(c, "repeat");
}

/** Irregular octagons, like the invitation's overlapping gold frames. */
function frames(): Frame[] {
  return [0, 1, 2].map((i) => ({
    ph: i * 2.1,
    pts: Array.from({ length: 8 }, (_, j) => ({ a: (j / 8) * Math.PI * 2 + rand(-0.12, 0.12) + i * 0.2, k: rand(0.9, 1.06) })),
  }));
}

export const blush = canvasBackground<State>({
  id: "blush",
  label: "Blush & roses",
  swatch: "radial-gradient(circle at 50% 50%,#fff 30%,#f7c9be 65%,#d9b468)",
  themes: ["roses"],
  setup(w, h) {
    const m = Math.min(w, h);
    const imgs = [clusterImage(), clusterImage(), clusterImage()];
    const probe = document.createElement("canvas").getContext("2d");
    return {
      washes: WASHES.map((c, i) => ({
        c, ph: i * 1.7, r: Math.max(w, h) * rand(0.3, 0.5),
        ax: rand(0.1, 0.25), ay: rand(0.08, 0.2), cx: rand(0.1, 0.9), cy: rand(0.1, 0.9),
      })),
      frames: frames(),
      // top-left (beside the title), right edge, bottom centre; the QR card sits top-right
      clusters: [
        { img: imgs[0]!, x: w * 0.02, y: h * 0.18, size: m * 0.3 },
        { img: imgs[1]!, x: w * 0.86, y: h * 0.42, size: m * 0.26 },
        { img: imgs[2]!, x: w * 0.44, y: h * 0.74, size: m * 0.28 },
      ],
      paper: probe ? paperPattern(probe) : null,
    };
  },
  frame(ctx, s, w, h, t) {
    ctx.fillStyle = "#fbeee9";
    ctx.fillRect(0, 0, w, h);
    for (const b of s.washes) {
      const x = w * (b.cx + Math.sin(t * 0.03 + b.ph) * b.ax);
      const y = h * (b.cy + Math.cos(t * 0.04 + b.ph) * b.ay);
      const g = ctx.createRadialGradient(x, y, 0, x, y, b.r);
      g.addColorStop(0, `rgba(${b.c},0.55)`);
      g.addColorStop(1, `rgba(${b.c},0)`);
      ctx.fillStyle = g;
      ctx.fillRect(0, 0, w, h);
    }

    const cx = w / 2, cy = h * 0.54, r = Math.min(w, h) * 0.46;
    const glow = ctx.createRadialGradient(cx, cy, r * 0.82, cx, cy, r);
    glow.addColorStop(0, "rgba(255,255,255,0.9)");
    glow.addColorStop(1, "rgba(255,255,255,0)");
    ctx.fillStyle = glow;
    ctx.beginPath();
    ctx.arc(cx, cy, r, 0, Math.PI * 2);
    ctx.fill();

    const gold = ctx.createLinearGradient(cx - r, cy - r, cx + r, cy + r);
    gold.addColorStop(0, "#c9a24f");
    gold.addColorStop(0.5, "#ead39a");
    gold.addColorStop(1, "#b8873e");
    ctx.strokeStyle = gold;
    ctx.lineWidth = 1.6;
    ctx.globalAlpha = 0.85;
    const rx = Math.min(w * 0.42, r * 1.5), ry = r * 1.04;
    for (const f of s.frames) {
      const turn = Math.sin(t * 0.05 + f.ph) * 0.04;
      ctx.beginPath();
      f.pts.forEach((p, i) => {
        const x = cx + Math.cos(p.a + turn) * rx * p.k, y = cy + Math.sin(p.a + turn) * ry * p.k;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.closePath();
      ctx.stroke();
    }
    ctx.globalAlpha = 1;

    for (const c of s.clusters) {
      if (c.img.complete) ctx.drawImage(c.img, c.x, c.y + Math.sin(t * 0.3 + c.x) * 2, c.size, c.size);
    }
    if (s.paper) {
      ctx.fillStyle = s.paper;
      ctx.fillRect(0, 0, w, h);
    }
  },
});
