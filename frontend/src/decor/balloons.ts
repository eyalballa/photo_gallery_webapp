import { pick, rand } from "../lib/random";

const MAX_BALLOONS = 8;

function balloonSvg(color: string): string {
  return `<svg viewBox="0 0 60 130" xmlns="http://www.w3.org/2000/svg">
    <path d="M30 70 C 24 88, 38 100, 28 128" stroke="rgba(255,255,255,.5)" stroke-width="1.5" fill="none"/>
    <ellipse cx="30" cy="34" rx="26" ry="31" fill="${color}"/>
    <path d="M26 64 L34 64 L30 71 Z" fill="${color}"/>
    <ellipse cx="21" cy="22" rx="5" ry="9" fill="rgba(255,255,255,.4)" transform="rotate(-25 21 22)"/>
  </svg>`;
}

function launch(host: HTMLElement, palette: readonly string[]): void {
  if (host.childElementCount > MAX_BALLOONS) return;
  const el = document.createElement("div");
  const size = rand(40, 80);
  el.style.cssText = `position:absolute;left:0;top:0;width:${size}px;opacity:.85`;
  el.innerHTML = balloonSvg(pick(palette));
  host.appendChild(el);
  const w = window.innerWidth;
  const h = window.innerHeight;
  const x = rand(0, w - size);
  const sway = rand(-80, 80);
  const anim = el.animate(
    [
      { transform: `translate(${x}px, ${h + 20}px) rotate(-4deg)` },
      { transform: `translate(${x + sway}px, ${h * 0.45}px) rotate(5deg)` },
      { transform: `translate(${x - sway / 2}px, ${-size * 2.4}px) rotate(-3deg)` },
    ],
    { duration: rand(16000, 26000), easing: "linear" },
  );
  anim.onfinish = () => el.remove();
}

/** Rising balloons in the theme's palette. Returns an unmount function. */
export function mountBalloons(host: HTMLElement, palette: readonly string[]): () => void {
  const timers = [0, 1, 2].map((i) => window.setTimeout(() => launch(host, palette), i * 900));
  const interval = window.setInterval(() => launch(host, palette), 3200);
  return () => {
    timers.forEach((t) => window.clearTimeout(t));
    window.clearInterval(interval);
    host.replaceChildren();
  };
}
