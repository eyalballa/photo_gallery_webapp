import type { Background } from "../types";

/** The viewer's own picture, chosen in the settings drawer, with a dark wash so photos stand out. */
export const image: Background = {
  id: "image",
  label: "Your image",
  swatch: "repeating-linear-gradient(45deg,#a9a8cf 0 4px,#1b2160 4px 8px)",
  themes: ["kids", "grown", "roses"],
  mount(host, { imageUrl }) {
    const el = document.createElement("div");
    el.className = "img-bg";
    if (imageUrl) el.style.backgroundImage = `url("${imageUrl}")`;
    host.appendChild(el);
    return () => el.remove();
  },
};
