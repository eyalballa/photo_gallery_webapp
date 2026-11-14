// Client-only structs (DESIGN.md §6.1, §6.2). API payload types live in api/schema.d.ts.
import type { ReactNode } from "react";

/** A photo the wall can show, mapped from the API's PhotoOut. */
export interface WallPhoto {
  id: string;
  url: string;
  width: number;
  height: number;
  aged: boolean;
  version: number;
  firstSeen: string;
}

/** What the queue needs to rank a photo. */
export interface QueueEntry {
  id: string;
  isNew: boolean;
  shownCount: number;
}

/** Card geometry, in CSS pixels. */
export interface CardLayout {
  imgW: number;
  imgH: number;
  pad: number;
  padB: number;
  cardW: number;
  cardH: number;
  y: number;
}

/** Per-card CSS bob/tilt parameters. */
export interface BobParams {
  durationS: number;
  delayS: number;
  r1Deg: number;
  r2Deg: number;
}

/** One polaroid in flight. Position at time t: x0 - v * (t - startedAt) / 1000. */
export interface CardState {
  key: number;
  photoId: string;
  showNewMarker: boolean;
  layout: CardLayout;
  bob: BobParams;
  x0: number;
  x1: number;
  v: number;
  startedAt: number;
  /** Space in px the next card leaves behind this one (random per card). */
  gap: number;
}

export interface Viewport {
  width: number;
  height: number;
  headerBottom: number;
}

export interface Theme {
  id: string;
  label: string;
  /** Not in DESIGN §6.2: a CSS background used for the option chip in the settings drawer. */
  swatch: string;
  tokens: Record<string, string>;
  fonts: string[];
  palette: string[];
  defaultBackground: string;
  decor: "balloons" | "petals" | null;
  newLabel: string;
  qrCaption: string;
  renderTitle(text: string): ReactNode;
  motion: { tilt: number; bob: number };
}

export interface BackgroundContext {
  palette: string[];
  reducedMotion: boolean;
  /** Not in DESIGN §6.2: the viewer-chosen image for the "image" background. */
  imageUrl: string | null;
}

export interface Background {
  id: string;
  label: string;
  /** Not in DESIGN §6.2: settings-drawer chip. */
  swatch: string;
  themes: string[];
  mount(host: HTMLElement, ctx: BackgroundContext): () => void;
}

/** Effective wall settings: config defaults with local overrides applied. */
export interface WallSettings {
  theme: string;
  background: string;
  crossingSeconds: number;
  decorations: boolean;
  newMarker: boolean;
}

/** What the settings drawer saves to localStorage, on top of config defaults. */
export interface SettingsOverrides {
  theme?: string;
  backgrounds?: Record<string, string>;
  crossingSeconds?: number;
  decorations?: boolean;
}
