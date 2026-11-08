import type { Theme } from "../types";
import { grown } from "./grown";
import { kids } from "./kids";
import { roses } from "./roses";

export const THEMES: readonly Theme[] = [kids, grown, roses];

export function getTheme(id: string): Theme {
  return THEMES.find((t) => t.id === id) ?? kids;
}
