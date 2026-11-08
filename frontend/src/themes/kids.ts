import { createElement, type CSSProperties, type ReactNode } from "react";
import type { Theme } from "../types";

const PALETTE = ["#ff5d73", "#ffc145", "#4cc9f0", "#7ae582", "#b388ff"]; // coral, sun, sky, mint, grape

/** One color per letter, each letter waving a little after the previous one. */
function renderTitle(text: string): ReactNode {
  let i = 0;
  return text.split(" ").map((word, w) =>
    createElement(
      "span",
      { className: "word", key: w, "aria-hidden": true },
      [...word].map((ch) => {
        const style = { "--i": i, color: PALETTE[i % PALETTE.length] } as CSSProperties;
        return createElement("span", { className: "ch", key: i++, style }, ch);
      }),
    ),
  );
}

export const kids: Theme = {
  id: "kids",
  label: "Kids party",
  swatch: "linear-gradient(135deg,#ff5d73,#ffc145,#4cc9f0)",
  tokens: {
    "--ink": "#0e1230",
    "--paper": "#fbf7ee",
    "--paper-aged": "#efe2c4",
    "--text": "#f4f2ff",
    "--muted": "#a9a8cf",
    "--accent": "#ffc145",
    "--panel": "rgba(14, 18, 48, 0.94)",
    "--line": "rgba(169, 168, 207, 0.22)",
    "--font-display": '"Lilita One", "Arial Rounded MT Bold", "Trebuchet MS", system-ui, sans-serif',
    "--font-ui": '"Fredoka", "Avenir Next", system-ui, sans-serif',
  },
  fonts: ["Lilita One", "Fredoka:wght@400;500;600"],
  palette: PALETTE,
  defaultBackground: "party-night",
  decor: "balloons",
  newLabel: "NEW",
  qrCaption: "Add your photos!",
  renderTitle,
  motion: { tilt: 1, bob: 1 },
};
