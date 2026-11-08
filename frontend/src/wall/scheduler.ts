// Queue order and spawn rules (DESIGN.md §6.4). Pure: state in, decision out.
// Time (`now`, ms) and randomness (`rng`, returns [0, 1)) are always passed in.
import type { CardLayout, CardState, QueueEntry, Viewport, WallPhoto } from "../types";

export type Rng = () => number;

export const GAP_FRACTION = 0.04;
export const EXIT_MARGIN_PX = 60;
export const ENTRY_OFFSET_PX = 10;

export interface SchedulerState {
  cards: CardState[];
  /** Times each photo was shown this session. A missing id means the photo is new. */
  shown: Record<string, number>;
  placeHigh: boolean;
  nextKey: number;
  /** The photo picked to enter next, kept across ticks so it can be pre-decoded before its slot opens. */
  nextId: string | null;
}

export interface SchedulerEnv {
  now: number;
  viewport: Viewport;
  crossingSeconds: number;
  rng: Rng;
}

export type Decision =
  | { type: "none"; state: SchedulerState }
  | { type: "load"; photoId: string; state: SchedulerState }
  | { type: "spawn"; card: CardState; state: SchedulerState };

export function initialState(placeHigh: boolean): SchedulerState {
  return { cards: [], shown: {}, placeHigh, nextKey: 1, nextId: null };
}

/** Photos already in the album at startup are not "new"; only later arrivals jump the queue. */
export function withBaseline(state: SchedulerState, ids: readonly string[]): SchedulerState {
  const shown = { ...state.shown };
  for (const id of ids) shown[id] ??= 0;
  return { ...state, shown };
}

export function queueEntries(photos: readonly WallPhoto[], shown: Record<string, number>): QueueEntry[] {
  return photos.map((p) => ({ id: p.id, isNew: shown[p.id] === undefined, shownCount: shown[p.id] ?? 0 }));
}

/** `isNew desc, shownCount asc, random`, with excluded (on-screen) ids left out. */
export function queueOrder(entries: readonly QueueEntry[], exclude: ReadonlySet<string>, rng: Rng): string[] {
  return entries
    .filter((e) => !exclude.has(e.id))
    .map((e) => ({ e, r: rng() }))
    .sort((a, b) => Number(b.e.isNew) - Number(a.e.isNew) || a.e.shownCount - b.e.shownCount || a.r - b.r)
    .map(({ e }) => e.id);
}

/** From just below the header to 97% of the height. */
export function usableBand(vp: Viewport): { top: number; bottom: number } {
  return { top: vp.headerBottom + vp.height * 0.02, bottom: vp.height * 0.97 };
}

/** One shared speed in px/s, so cards never catch up with each other. */
export function driftSpeed(vp: Viewport, crossingSeconds: number): number {
  return (vp.width + 0.7 * vp.height) / crossingSeconds;
}

/** Image ≈ 56% of the band (±5%), padding 4.5% sides / 20% bottom; top or bottom 25% of the slack. */
export function layoutCard(size: { width: number; height: number }, vp: Viewport, placeHigh: boolean, rng: Rng): CardLayout {
  const { top, bottom } = usableBand(vp);
  const band = bottom - top;
  const imgH = band * 0.56 * (0.95 + rng() * 0.1);
  const imgW = (imgH * size.width) / size.height;
  const pad = imgH * 0.045;
  const padB = imgH * 0.2;
  const cardW = imgW + pad * 2;
  const cardH = imgH + pad + padB;
  const slack = Math.max(band - cardH, 0);
  const y = top + slack * (placeHigh ? rng() * 0.25 : 0.75 + rng() * 0.25);
  return { imgW, imgH, pad, padB, cardW, cardH, y };
}

export function cardX(card: CardState, now: number): number {
  return card.x0 - (card.v * (now - card.startedAt)) / 1000;
}

export function cardDurationMs(card: CardState): number {
  return ((card.x0 - card.x1) / card.v) * 1000;
}

/** The last card has fully entered plus a 4% gap. Spacing alone decides, so how many photos are on
 * screen follows the screen's width and the photos' shapes: a fixed maximum left holes whenever narrow
 * (portrait) cards needed more than the maximum to fill the screen.
 * If the speed went up since the last card entered (settings drawer, resize), also wait until the
 * new card can't catch it before it leaves the screen. */
export function canSpawn(cards: readonly CardState[], env: SchedulerEnv): boolean {
  const last = cards[cards.length - 1];
  if (!last) return true;
  const gap = env.viewport.width * GAP_FRACTION;
  const trailing = cardX(last, env.now) + last.layout.cardW;
  if (trailing > env.viewport.width - gap) return false;
  const v = driftSpeed(env.viewport, env.crossingSeconds);
  if (v <= last.v) return true;
  const exitS = (cardX(last, env.now) - last.x1) / last.v;
  return env.viewport.width + ENTRY_OFFSET_PX - v * exitS >= trailing - last.v * exitS;
}

export function createCard(
  state: SchedulerState,
  env: SchedulerEnv,
  photo: WallPhoto,
  x0: number,
): { state: SchedulerState; card: CardState } {
  const layout = layoutCard(photo, env.viewport, state.placeHigh, env.rng);
  const { rng } = env;
  const card: CardState = {
    key: state.nextKey,
    photoId: photo.id,
    showNewMarker: state.shown[photo.id] === undefined,
    layout,
    bob: { durationS: 4 + rng() * 2, delayS: rng() * 5, r1Deg: -5 + rng() * 6, r2Deg: -1 + rng() * 6 },
    x0,
    x1: -layout.cardW - EXIT_MARGIN_PX,
    v: driftSpeed(env.viewport, env.crossingSeconds),
    startedAt: env.now,
  };
  return {
    card,
    state: {
      cards: [...state.cards, card],
      shown: { ...state.shown, [photo.id]: (state.shown[photo.id] ?? 0) + 1 },
      placeHigh: !state.placeHigh,
      nextKey: state.nextKey + 1,
      nextId: null,
    },
  };
}

/** The queue head. A previously picked `nextId` is kept while it still ranks first (same isNew and
 * shownCount as the head), so random tie-breaks don't change the pick on every tick. */
export function pickNext(state: SchedulerState, photos: readonly WallPhoto[], rng: Rng): { photo?: WallPhoto; state: SchedulerState } {
  const onScreen = new Set(state.cards.map((c) => c.photoId));
  const entries = queueEntries(photos, state.shown).filter((e) => !onScreen.has(e.id));
  const pinned = entries.find((e) => e.id === state.nextId);
  const headId = queueOrder(entries, onScreen, rng)[0];
  const head = entries.find((e) => e.id === headId);
  const id = pinned && head && pinned.isNew === head.isNew && pinned.shownCount === head.shownCount ? pinned.id : headId;
  const photo = photos.find((p) => p.id === id);
  const nextId = photo?.id ?? null;
  return { photo, state: nextId === state.nextId ? state : { ...state, nextId } };
}

/** Called on a timer: load the next photo ahead of time, spawn it at the right edge when there's room, or wait. */
export function tick(
  state: SchedulerState,
  photos: readonly WallPhoto[],
  env: SchedulerEnv,
  isReady: (photoId: string) => boolean,
): Decision {
  const { photo, state: s } = pickNext(state, photos, env.rng);
  if (!photo) return { type: "none", state: s };
  if (!isReady(photo.id)) return { type: "load", photoId: photo.id, state: s };
  if (!canSpawn(s.cards, env)) return { type: "none", state: s };
  return { type: "spawn", ...createCard(s, env, photo, env.viewport.width + ENTRY_OFFSET_PX) };
}

/** Startup: place cards mid-flight from 3% of the width to the right edge so the first frame is a full wall.
 * (Stopping at 80% left a hole of up to a quarter of the screen until it scrolled away.) */
export function seed(state: SchedulerState, photos: readonly WallPhoto[], env: SchedulerEnv): SchedulerState {
  const gap = env.viewport.width * GAP_FRACTION;
  let x = env.viewport.width * 0.03;
  let next = state;
  while (x < env.viewport.width) {
    const { photo, state: picked } = pickNext(next, photos, env.rng);
    if (!photo) break;
    const made = createCard(picked, env, photo, x);
    next = made.state;
    x += made.card.layout.cardW + gap;
  }
  return next;
}

/** Drop cards that have left the screen, or whose photo is gone (removed from the album). */
export function prune(state: SchedulerState, now: number, liveIds: ReadonlySet<string>): SchedulerState {
  const cards = state.cards.filter((c) => liveIds.has(c.photoId) && now < c.startedAt + cardDurationMs(c));
  return cards.length === state.cards.length ? state : { ...state, cards };
}
