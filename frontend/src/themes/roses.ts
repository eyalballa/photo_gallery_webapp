import type { Theme } from "../types";

// pink, blush, gold, white, sage: the invitation's roses, gold frame and leaves
const PALETTE = ["#ec7ab3", "#f6b8cf", "#d9b468", "#ffffff", "#a9bb8f"];

export const roses: Theme = {
  id: "roses",
  label: "Roses & gold",
  swatch: "linear-gradient(135deg,#fbe9e4,#ec7ab3 55%,#d9b468)",
  tokens: {
    "--ink": "#fbeee9",
    "--paper": "#ffffff",
    "--paper-aged": "#f4e6d6",
    "--text": "#7a4b55",
    "--muted": "#a6838a",
    "--accent": "#ec7ab3",
    "--rose-deep": "#d9649f",
    "--gold": "#c9a24f",
    "--panel": "rgba(255, 248, 246, 0.96)",
    "--line": "rgba(122, 75, 85, 0.18)",
    // Hebrew-capable, so a Hebrew title renders in the theme's fonts
    "--font-display": '"Secular One", "Arial Rounded MT Bold", system-ui, sans-serif',
    "--font-ui": '"Assistant", "Avenir Next", system-ui, sans-serif',
  },
  fonts: ["Secular One", "Assistant:wght@400;600;700"],
  palette: PALETTE,
  defaultBackground: "blush",
  decor: "petals",
  newLabel: "New",
  qrCaption: "Add your photos",
  renderTitle: (text) => text, // outline + offset shadow are CSS (body[data-look="roses"] .header h1)
  motion: { tilt: 0.5, bob: 0.7 },
};
