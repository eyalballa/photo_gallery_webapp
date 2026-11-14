import { describe, expect, it } from "vitest";
import type { CardState, Viewport, WallPhoto } from "../types";
import {
  canSpawn,
  createCard,
  driftSpeed,
  initialState,
  layoutCard,
  prune,
  queueEntries,
  queueOrder,
  seed,
  tick,
  withBaseline,
  type SchedulerEnv,
} from "./scheduler";

// 1600×1000 with an 80 px header: band runs 100 → 970 (870 px).
const vp: Viewport = { width: 1600, height: 1000, headerBottom: 80 };
const half = () => 0.5;
const env = (over: Partial<SchedulerEnv> = {}): SchedulerEnv => ({
  now: 0, viewport: vp, crossingSeconds: 23, rng: half, ...over,
});
const photo = (id: string): WallPhoto => ({
  id, url: `/media/${id}.jpg?v=1`, width: 1000, height: 1000, aged: false, version: 1, firstSeen: "2026-11-06T12:00:00Z",
});
const card = (over: Partial<CardState>): CardState => ({
  key: 1, photoId: "p", showNewMarker: false,
  layout: { imgW: 0, imgH: 0, pad: 0, padB: 0, cardW: 500, cardH: 0, y: 0 },
  bob: { durationS: 5, delayS: 0, r1Deg: 0, r2Deg: 0 },
  x0: 1610, x1: -560, v: 100, startedAt: 0, gap: 64, ...over,
});
const sequence = (...values: number[]) => () => values.shift() ?? 0;

describe("queueOrder", () => {
  it("puts new photos first, then least shown", () => {
    const entries = [
      { id: "b", isNew: false, shownCount: 2 },
      { id: "a", isNew: false, shownCount: 1 },
      { id: "new-1", isNew: true, shownCount: 0 },
    ];
    expect(queueOrder(entries, new Set(), half)).toEqual(["new-1", "a", "b"]);
  });

  it("excludes photos already on screen", () => {
    const entries = [{ id: "a", isNew: false, shownCount: 0 }, { id: "b", isNew: false, shownCount: 0 }];
    expect(queueOrder(entries, new Set(["a"]), half)).toEqual(["b"]);
  });

  it("breaks ties randomly", () => {
    const entries = ["a", "b", "c"].map((id) => ({ id, isNew: false, shownCount: 0 }));
    expect(queueOrder(entries, new Set(), sequence(0.9, 0.1, 0.5))).toEqual(["b", "c", "a"]);
  });
});

describe("queueEntries", () => {
  it("treats baseline photos as not new and unseen arrivals as new", () => {
    const state = withBaseline(initialState(true), ["old"]);
    expect(queueEntries([photo("old"), photo("fresh")], state.shown)).toEqual([
      { id: "old", isNew: false, shownCount: 0 },
      { id: "fresh", isNew: true, shownCount: 0 },
    ]);
  });
});

describe("geometry", () => {
  it("uses one shared speed of (W + 0.7·H) / crossing seconds", () => {
    expect(driftSpeed(vp, 23)).toBe(100);
  });

  it("sizes the image at 56% of the band with polaroid padding", () => {
    const l = layoutCard({ width: 1000, height: 1000 }, vp, true, half);
    expect(l.imgH).toBeCloseTo(487.2);
    expect(l.pad).toBeCloseTo(21.924);
    expect(l.padB).toBeCloseTo(97.44);
    expect(l.cardW).toBeCloseTo(531.048);
  });

  it("places high cards in the top quarter of the slack and low cards in the bottom quarter", () => {
    expect(layoutCard({ width: 1000, height: 1000 }, vp, true, half).y).toBeCloseTo(132.9295);
    expect(layoutCard({ width: 1000, height: 1000 }, vp, false, half).y).toBeCloseTo(330.5065);
  });
});

describe("canSpawn", () => {
  it("goes by spacing alone, however many cards are already on screen", () => {
    // Five narrow cards; the last one's trailing edge (800 + 300) is past the 1536 entry line.
    const narrow = [-100, 125, 350, 575, 800].map((x0) => card({ x0, layout: { ...card({}).layout, cardW: 300 } }));
    expect(canSpawn(narrow, env())).toBe(true);
  });

  it("waits until the last card has fully entered plus its gap", () => {
    // Trailing edge must reach 1600 - 64 = 1536: x0 1610 → 1036 takes 5.74 s at 100 px/s.
    expect(canSpawn([card({})], env({ now: 5000 }))).toBe(false);
    expect(canSpawn([card({})], env({ now: 6000 }))).toBe(true);
    // A wider gap (192 px, 12%) waits longer: trailing edge 1408 at 7.02 s.
    expect(canSpawn([card({ gap: 192 })], env({ now: 6000 }))).toBe(false);
    expect(canSpawn([card({ gap: 192 })], env({ now: 7100 }))).toBe(true);
  });

  it("after a speed-up, waits until the faster card can't catch the last one before it leaves", () => {
    // Last card at 100 px/s; new cards at 200 px/s (crossing 11.5 s). The new card only stays clear once the
    // last card's left edge is at x ≤ 275, i.e. from 13.35 s.
    expect(canSpawn([card({})], env({ now: 13000, crossingSeconds: 11.5 }))).toBe(false);
    expect(canSpawn([card({})], env({ now: 14000, crossingSeconds: 11.5 }))).toBe(true);
  });
});

describe("tick", () => {
  it("asks for the next photo to be loaded before it can enter", () => {
    const d = tick(initialState(true), [photo("a")], env(), () => false);
    expect([d.type, d.type === "load" && d.photoId, d.state.nextId]).toEqual(["load", "a", "a"]);
  });

  it("loads the next photo while the last card is still entering", () => {
    const state = { ...initialState(true), cards: [card({ photoId: "on" })] };
    expect(tick(state, [photo("on"), photo("a")], env({ now: 1000 }), () => false).type).toBe("load");
  });

  it("keeps the same pick across ticks while it is tied with the head", () => {
    const photos = ["a", "b", "c"].map(photo);
    const first = tick(withBaseline(initialState(true), ["a", "b", "c"]), photos, env({ rng: sequence(0.9, 0.1, 0.5) }), () => false);
    const second = tick(first.state, photos, env({ rng: sequence(0.1, 0.9, 0.5) }), () => false);
    expect([first.state.nextId, second.state.nextId]).toEqual(["b", "b"]);
  });

  it("lets a newly arrived photo replace the pick", () => {
    const state = { ...withBaseline(initialState(true), ["a"]), nextId: "a" };
    expect(tick(state, [photo("a"), photo("fresh")], env(), () => false).state.nextId).toBe("fresh");
  });

  it("spawns at the right edge with the new marker on first appearance only", () => {
    const first = tick(initialState(true), [photo("a")], env(), () => true);
    if (first.type !== "spawn") throw new Error("expected spawn");
    expect([first.card.x0, first.card.v, first.card.showNewMarker]).toEqual([1610, 100, true]);

    const later = tick({ ...first.state, cards: [] }, [photo("a")], env(), () => true);
    if (later.type !== "spawn") throw new Error("expected spawn");
    expect([later.card.showNewMarker, later.state.shown]).toEqual([false, { a: 2 }]);
  });

  it("alternates high and low placement", () => {
    const a = tick(initialState(true), [photo("a"), photo("b")], env(), () => true);
    if (a.type !== "spawn") throw new Error("expected spawn");
    const b = tick(a.state, [photo("a"), photo("b")], env({ now: 60000 }), () => true);
    if (b.type !== "spawn") throw new Error("expected spawn");
    expect([a.card.layout.y, b.card.layout.y].map(Math.round)).toEqual([133, 331]);
  });
});

describe("createCard", () => {
  it("draws each card's gap between 2% and 12% of the width", () => {
    const gap = (r: number) => createCard(initialState(true), env({ rng: () => r }), photo("a"), 0).card.gap;
    expect([gap(0), gap(0.5), gap(0.999999)].map(Math.round)).toEqual([32, 112, 192]);
  });
});

describe("seed", () => {
  it("places cards mid-flight from 3% of the width with each card's gap, up to the right edge", () => {
    // Narrow (3:4) cards: 409 px wide + a 112 px gap (7%, rng 0.5). A fourth would start at 1611, off screen.
    const photos = ["a", "b", "c", "d", "e"].map((id) => ({ ...photo(id), width: 750 }));
    const state = seed(initialState(true), photos, env());
    expect(state.cards.map((c) => Math.round(c.x0))).toEqual([48, 569, 1090]);
  });
});

describe("prune", () => {
  it("drops cards that have exited or whose photo was removed", () => {
    // 1610 → -560 at 100 px/s lasts 21.7 s.
    const state = { ...initialState(true), cards: [card({ key: 1, photoId: "a" }), card({ key: 2, photoId: "b", startedAt: 20000 }), card({ key: 3, photoId: "gone", startedAt: 20000 })] };
    expect(prune(state, 22000, new Set(["a", "b"])).cards.map((c) => c.key)).toEqual([2]);
  });
});
