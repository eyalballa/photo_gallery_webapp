import type { Theme } from "../types";

export const grown: Theme = {
  id: "grown",
  label: "Young adult",
  swatch: "linear-gradient(135deg,#e3c193,#a8546a,#120c16)",
  tokens: {
    "--ink": "#120c16",
    "--paper": "#f5f1ea",
    "--paper-aged": "#e9dcc3",
    "--text": "#f2ece4",
    "--muted": "#a99ca6",
    "--accent": "#e3c193",
    "--panel": "rgba(18, 12, 22, 0.95)",
    "--line": "rgba(227, 193, 147, 0.2)",
    "--font-display": '"Fraunces", "Iowan Old Style", Georgia, serif',
    "--font-ui": '"Manrope", "Avenir Next", system-ui, sans-serif',
  },
  fonts: ["Fraunces:opsz,wght@9..144,600;9..144,800", "Manrope:wght@400;500;600"],
  palette: ["#e3c193", "#c97b84", "#f5f1ea", "#b08d57", "#8e5a7a"], // champagne, rose, cream, antique gold, plum
  defaultBackground: "velvet",
  decor: "balloons",
  newLabel: "Just added",
  qrCaption: "Scan to add photos",
  renderTitle: (text) => text, // one color; the gold rule underneath is CSS (body[data-look="grown"] h1::after)
  motion: { tilt: 0.6, bob: 0.8 },
};
