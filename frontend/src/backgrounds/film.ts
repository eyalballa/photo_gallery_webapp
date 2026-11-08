import { canvasBackground } from "./canvas";

interface FilmState { noise: HTMLCanvasElement; pattern: CanvasPattern | null }

const NOISE = 160;

function makeNoise(): HTMLCanvasElement {
  const n = document.createElement("canvas");
  n.width = n.height = NOISE;
  const nctx = n.getContext("2d");
  if (!nctx) return n;
  const img = nctx.createImageData(NOISE, NOISE);
  for (let i = 0; i < img.data.length; i += 4) {
    const v = Math.random() * 255;
    img.data[i] = img.data[i + 1] = img.data[i + 2] = v;
    img.data[i + 3] = 16;
  }
  nctx.putImageData(img, 0, 0);
  return n;
}

export const film = canvasBackground<FilmState>({
  id: "film",
  label: "Film night",
  swatch: "linear-gradient(135deg,#6b3a22,#1c1512 50%,#0d0a09)",
  themes: ["grown"],
  setup() {
    return { noise: makeNoise(), pattern: null };
  },
  frame(ctx, st, w, h, t, dt) {
    const g = ctx.createLinearGradient(0, 0, w, h);
    g.addColorStop(0, "#22180f");
    g.addColorStop(1, "#0b0908");
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, w, h);
    const leak = ctx.createRadialGradient(w * 1.02, h * 0.1, 0, w * 1.02, h * 0.1, w * 0.55);
    leak.addColorStop(0, `rgba(230,120,60,${0.2 + 0.07 * Math.sin(t * 0.5)})`);
    leak.addColorStop(1, "rgba(230,120,60,0)");
    ctx.fillStyle = leak;
    ctx.fillRect(0, 0, w, h);
    st.pattern ??= ctx.createPattern(st.noise, "repeat");
    if (!st.pattern) return;
    // Grain jitters every frame; under reduced motion (dt slowed) it holds still.
    const still = dt < 0.01;
    const ox = still ? 0 : Math.random() * NOISE;
    const oy = still ? 0 : Math.random() * NOISE;
    ctx.save();
    ctx.translate(-ox, -oy);
    ctx.fillStyle = st.pattern;
    ctx.fillRect(0, 0, w + NOISE, h + NOISE);
    ctx.restore();
  },
});
