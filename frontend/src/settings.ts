// Effective settings = config defaults + overrides saved in this browser (DESIGN.md §6.5).
import type { WallConfig } from "./api/client";
import { getBackground } from "./backgrounds";
import { storage } from "./lib/storage";
import { getTheme } from "./themes";
import type { SettingsOverrides, WallSettings } from "./types";

const SETTINGS_KEY = "wall.settings";
const IMAGE_KEY = "wall.bgImage";

const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, Math.round(v)));

export function resolveSettings(config: WallConfig, o: SettingsOverrides, hasImage: boolean): WallSettings {
  const theme = getTheme(o.theme ?? config.theme);
  const wanted = o.backgrounds?.[theme.id] ?? (theme.id === config.theme ? config.background : null);
  const bg = wanted ? getBackground(wanted) : undefined;
  const usable = bg && bg.themes.includes(theme.id) && (bg.id !== "image" || hasImage);
  return {
    theme: theme.id,
    background: usable ? bg.id : theme.defaultBackground,
    crossingSeconds: clamp(o.crossingSeconds ?? config.crossing_seconds, 8, 60),
    maxOnScreen: clamp(o.maxOnScreen ?? config.max_on_screen, 1, 4),
    decorations: o.decorations ?? config.decorations,
    newMarker: config.new_marker,
  };
}

function isRecordOfStrings(v: unknown): v is Record<string, string> {
  return typeof v === "object" && v !== null && Object.values(v).every((x) => typeof x === "string");
}

/** Reads only well-typed fields; anything malformed is ignored. */
export function parseOverrides(raw: string | null): SettingsOverrides {
  if (!raw) return {};
  let data: unknown;
  try {
    data = JSON.parse(raw);
  } catch {
    return {};
  }
  if (typeof data !== "object" || data === null) return {};
  const d = data as Record<string, unknown>;
  const out: SettingsOverrides = {};
  if (typeof d.theme === "string") out.theme = d.theme;
  if (isRecordOfStrings(d.backgrounds)) out.backgrounds = d.backgrounds;
  if (typeof d.crossingSeconds === "number") out.crossingSeconds = d.crossingSeconds;
  if (typeof d.maxOnScreen === "number") out.maxOnScreen = d.maxOnScreen;
  if (typeof d.decorations === "boolean") out.decorations = d.decorations;
  return out;
}

export const loadOverrides = (): SettingsOverrides => parseOverrides(storage.get(SETTINGS_KEY));
export const saveOverrides = (o: SettingsOverrides): void => storage.set(SETTINGS_KEY, JSON.stringify(o));
export const clearOverrides = (): void => storage.remove(SETTINGS_KEY);

/** The "Your image" picture is a data URL; it may be too big to persist, in which case it lasts for this page load. */
export const loadImage = (): string | null => storage.get(IMAGE_KEY);
export const saveImage = (dataUrl: string): void => storage.set(IMAGE_KEY, dataUrl);
