import { useCallback, useEffect, useMemo, useRef, useState, type RefObject } from "react";
import type { CardState, Viewport, WallPhoto } from "../types";
import { ImageLoader } from "./imageLoader";
import { DriftingCard } from "./DriftingCard";
import { initialState, prune, seed, tick, withBaseline, type SchedulerEnv, type SchedulerState } from "./scheduler";

const TICK_MS = 250;
const SEED_WAIT_MS = 4000;

interface Props {
  photos: WallPhoto[];
  loaded: boolean;
  maxOnScreen: number;
  crossingSeconds: number;
  newLabel: string | null;
  headerRef: RefObject<HTMLElement | null>;
}

interface ShownCard {
  card: CardState;
  img: HTMLImageElement;
  aged: boolean;
}

function viewport(header: HTMLElement | null): Viewport {
  return { width: window.innerWidth, height: window.innerHeight, headerBottom: header?.getBoundingClientRect().bottom ?? 0 };
}

/** Runs the scheduler on a timer; React re-renders only when a card enters or leaves. */
export function CardsLayer({ photos, loaded, maxOnScreen, crossingSeconds, newLabel, headerRef }: Props) {
  const loader = useMemo(() => new ImageLoader(), []);
  const state = useRef<SchedulerState>(initialState(Math.random() < 0.5));
  const phase = useRef<{ baselined: boolean; seeded: boolean; loadedAt: number }>({ baselined: false, seeded: false, loadedAt: 0 });
  const [shown, setShown] = useState<ShownCard[]>([]);
  const latest = useRef({ photos, maxOnScreen, crossingSeconds });
  latest.current = { photos, maxOnScreen, crossingSeconds };

  const commit = useCallback((next: SchedulerState, added: ShownCard[] = []) => {
    const prev = state.current;
    state.current = next;
    if (next.cards === prev.cards && added.length === 0) return;
    const keys = new Set(next.cards.map((c) => c.key));
    setShown((cur) => [...cur.filter((s) => keys.has(s.card.key)), ...added]);
  }, []);

  const onDone = useCallback(
    (key: number) => commit({ ...state.current, cards: state.current.cards.filter((c) => c.key !== key) }),
    [commit],
  );

  useEffect(() => {
    if (!loaded) return;
    const step = () => {
      const now = performance.now();
      const { photos: all, maxOnScreen: max, crossingSeconds: crossing } = latest.current;
      const usable = all.filter((p) => !loader.isFailing(p.url, now));
      const byId = new Map(all.map((p) => [p.id, p]));
      const env: SchedulerEnv = { now, viewport: viewport(headerRef.current), maxOnScreen: max, crossingSeconds: crossing, rng: Math.random };
      const ph = phase.current;
      let s = prune(state.current, now, new Set(byId.keys()));

      if (!ph.baselined) {
        s = withBaseline(s, all.map((p) => p.id));
        ph.baselined = true;
        ph.loadedAt = now;
      }

      const takeCards = (cards: CardState[]): ShownCard[] =>
        cards.flatMap((card) => {
          const photo = byId.get(card.photoId);
          const img = photo && loader.take(photo.url);
          return photo && img ? [{ card, img, aged: photo.aged }] : [];
        });

      if (!ph.seeded) {
        const candidates = usable.slice(0, max + 1);
        candidates.forEach((p) => loader.load(p.url));
        const ready = usable.filter((p) => loader.isReady(p.url));
        const enough = ready.length >= Math.min(max, usable.length);
        if (usable.length === 0 || (!enough && now - ph.loadedAt < SEED_WAIT_MS)) return commit(s);
        ph.seeded = true;
        const seeded = seed(s, ready, env);
        return commit(seeded, takeCards(seeded.cards.slice(s.cards.length)));
      }

      const d = tick(s, usable, env, (id) => {
        const p = byId.get(id);
        return p !== undefined && loader.isReady(p.url);
      });
      const next = d.state.nextId === null ? undefined : byId.get(d.state.nextId);
      if (d.type === "load" && next) loader.load(next.url);
      const added = d.type === "spawn" ? takeCards([d.card]) : [];
      loader.retain(new Set(next && d.type !== "spawn" ? [next.url] : [])); // after take: a spawned image is the card's now
      commit(d.state, added);
    };
    step();
    const timer = window.setInterval(step, TICK_MS);
    return () => window.clearInterval(timer);
  }, [loaded, loader, headerRef, commit]);

  return (
    <div className="layer wall">
      {shown.map(({ card, img, aged }) => (
        <DriftingCard
          key={card.key}
          card={card}
          img={img}
          aged={aged}
          newLabel={card.showNewMarker ? newLabel : null}
          onDone={onDone}
        />
      ))}
    </div>
  );
}
