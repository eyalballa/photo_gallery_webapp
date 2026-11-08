import { useLayoutEffect, useRef, type CSSProperties } from "react";
import type { CardState } from "../types";
import { cardDurationMs } from "./scheduler";

interface Props {
  card: CardState;
  img: HTMLImageElement;
  aged: boolean;
  newLabel: string | null;
  onDone(key: number): void;
}

/** A polaroid drifting right → left. The drift is one WAAPI animation; bob and tilt are CSS. */
export function DriftingCard({ card, img, aged, newLabel, onDone }: Props) {
  const outer = useRef<HTMLDivElement>(null);
  const slot = useRef<HTMLDivElement>(null);
  const { layout, bob } = card;

  useLayoutEffect(() => {
    const host = slot.current;
    if (!host) return;
    img.style.width = `${layout.imgW}px`;
    img.style.height = `${layout.imgH}px`;
    host.appendChild(img);
    return () => img.remove();
  }, [img, layout.imgW, layout.imgH]);

  useLayoutEffect(() => {
    const el = outer.current;
    if (!el) return;
    const y = layout.y;
    const anim = el.animate(
      [{ transform: `translate3d(${card.x0}px, ${y}px, 0)` }, { transform: `translate3d(${card.x1}px, ${y}px, 0)` }],
      { duration: cardDurationMs(card), easing: "linear", fill: "forwards" },
    );
    anim.currentTime = Math.max(0, performance.now() - card.startedAt); // stay in sync with the scheduler's clock
    anim.onfinish = () => onDone(card.key);
    return () => anim.cancel();
  }, [card, layout.y, onDone]);

  const bobStyle = {
    "--bob-dur": `${bob.durationS.toFixed(2)}s`,
    "--bob-delay": `-${bob.delayS.toFixed(2)}s`,
    "--r1": `${bob.r1Deg.toFixed(1)}deg`,
    "--r2": `${bob.r2Deg.toFixed(1)}deg`,
  } as CSSProperties;
  const photoStyle = { "--pad": `${layout.pad}px`, "--pad-b": `${layout.padB}px` } as CSSProperties;

  return (
    <div className="card" ref={outer}>
      <div className="bob" style={bobStyle}>
        <figure className={aged ? "photo aged" : "photo"} style={photoStyle}>
          <div className="img-slot" ref={slot} />
          {newLabel && <div className="sticker">{newLabel}</div>}
        </figure>
      </div>
    </div>
  );
}
