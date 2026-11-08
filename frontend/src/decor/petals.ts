import { pick, rand } from "../lib/random";

const MAX_PETALS = 10;
const SHADES = ["#ec7ab3", "#f3a2c6", "#f6b8cf", "#e88fb6"];

function petalSvg(color: string): string {
  return `<svg viewBox="0 0 40 50" xmlns="http://www.w3.org/2000/svg">
    <path d="M20 2 C 34 10, 40 30, 20 48 C 0 30, 6 10, 20 2 Z" fill="${color}" opacity=".85"/>
    <path d="M20 8 C 26 18, 26 30, 20 42" stroke="rgba(255,255,255,.55)" stroke-width="1.5" fill="none"/>
  </svg>`;
}

function drop(host: HTMLElement): void {
  if (host.childElementCount > MAX_PETALS) return;
  const el = document.createElement("div");
  const size = rand(18, 34);
  el.style.cssText = `position:absolute;left:0;top:0;width:${size}px;opacity:.9`;
  el.innerHTML = petalSvg(pick(SHADES));
  host.appendChild(el);
  const w = window.innerWidth;
  const h = window.innerHeight;
  const x = rand(0, w);
  const sway = rand(60, 160);
  const spin = rand(-1, 1) > 0 ? 1 : -1;
  const anim = el.animate(
    [
      { transform: `translate(${x}px, ${-size * 2}px) rotate(0deg)` },
      { transform: `translate(${x + sway}px, ${h * 0.35}px) rotate(${120 * spin}deg)` },
      { transform: `translate(${x - sway / 2}px, ${h * 0.7}px) rotate(${240 * spin}deg)` },
      { transform: `translate(${x + sway / 3}px, ${h + size * 2}px) rotate(${360 * spin}deg)` },
    ],
    { duration: rand(14000, 22000), easing: "ease-in-out" },
  );
  anim.onfinish = () => el.remove();
}

/** Rose petals drifting down. Returns an unmount function. */
export function mountPetals(host: HTMLElement): () => void {
  const timers = [0, 1, 2].map((i) => window.setTimeout(() => drop(host), i * 1200));
  const interval = window.setInterval(() => drop(host), 2600);
  return () => {
    timers.forEach((t) => window.clearTimeout(t));
    window.clearInterval(interval);
    host.replaceChildren();
  };
}
