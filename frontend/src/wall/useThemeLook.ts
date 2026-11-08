import { useEffect } from "react";
import { ensureFonts } from "../lib/fonts";
import type { Theme } from "../types";

/** Applies a theme's tokens and motion multipliers as CSS custom properties on <body data-look>. */
export function useThemeLook(theme: Theme): void {
  useEffect(() => {
    ensureFonts(theme.fonts);
    const body = document.body;
    body.dataset.look = theme.id;
    const props: Record<string, string> = {
      ...theme.tokens,
      "--tilt-k": String(theme.motion.tilt),
      "--bob-k": String(theme.motion.bob),
    };
    for (const [k, v] of Object.entries(props)) body.style.setProperty(k, v);
    return () => {
      for (const k of Object.keys(props)) body.style.removeProperty(k);
    };
  }, [theme]);
}
