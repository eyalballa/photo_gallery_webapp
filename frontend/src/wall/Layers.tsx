import { useEffect, useRef } from "react";
import { getBackground } from "../backgrounds";
import { mountBalloons } from "../decor/balloons";
import { mountPetals } from "../decor/petals";
import type { Theme } from "../types";

interface BackgroundProps {
  id: string;
  palette: string[];
  reducedMotion: boolean;
  imageUrl: string | null;
}

export function BackgroundLayer({ id, palette, reducedMotion, imageUrl }: BackgroundProps) {
  const host = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const bg = getBackground(id);
    if (!host.current || !bg) return;
    return bg.mount(host.current, { palette, reducedMotion, imageUrl });
  }, [id, palette, reducedMotion, imageUrl]);
  return <div className="layer bg" ref={host} />;
}

interface DecorProps {
  kind: Theme["decor"];
  palette: string[];
}

/** The theme's decoration, or nothing when `kind` is null. */
export function DecorLayer({ kind, palette }: DecorProps) {
  const host = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!kind || !host.current) return;
    return kind === "petals" ? mountPetals(host.current) : mountBalloons(host.current, palette);
  }, [kind, palette]);
  return <div className="layer decor" ref={host} />;
}
