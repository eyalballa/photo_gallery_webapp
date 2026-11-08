import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { WallClient, WallConfig } from "../api/client";
import { useReducedMotion } from "../lib/useReducedMotion";
import { clearOverrides, loadImage, loadOverrides, resolveSettings, saveImage, saveOverrides } from "../settings";
import { getTheme } from "../themes";
import type { SettingsOverrides } from "../types";
import { CardsLayer } from "./CardsLayer";
import { Header } from "./Header";
import { BackgroundLayer, DecorLayer } from "./Layers";
import { SettingsDrawer } from "./SettingsDrawer";
import { goFullscreen, useKiosk } from "./useKiosk";
import { usePhotoFeed } from "./usePhotoFeed";
import { useThemeLook } from "./useThemeLook";

interface Props {
  client: WallClient;
  config: WallConfig;
  /** Called when the session stops being valid. */
  onLocked(): void;
}

/** Layers bottom → top: Background, Decor, Cards, Header; then the settings drawer. */
export function Wall({ client, config, onLocked }: Props) {
  const [overrides, setOverrides] = useState<SettingsOverrides>(loadOverrides);
  const [imageUrl, setImageUrl] = useState<string | null>(loadImage);
  const settings = useMemo(() => resolveSettings(config, overrides, imageUrl !== null), [config, overrides, imageUrl]);
  const theme = getTheme(settings.theme);
  const reducedMotion = useReducedMotion();
  const feed = usePhotoFeed(client);
  useEffect(() => {
    if (feed.unauthorized) onLocked();
  }, [feed.unauthorized, onLocked]);
  useEffect(() => {
    document.title = config.title;
  }, [config.title]);
  const headerRef = useRef<HTMLElement>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [hint, setHint] = useState(true);

  useThemeLook(theme);
  const toggleDrawer = useCallback(() => setDrawerOpen((o) => !o), []);
  const closeDrawer = useCallback(() => setDrawerOpen(false), []);
  useKiosk({ toggleDrawer, closeDrawer });
  useEffect(() => {
    const t = window.setTimeout(() => setHint(false), 7000);
    return () => window.clearTimeout(t);
  }, []);

  const update = useCallback((patch: SettingsOverrides) => {
    setOverrides((prev) => {
      const next = { ...prev, ...patch, backgrounds: { ...prev.backgrounds, ...patch.backgrounds } };
      saveOverrides(next);
      return next;
    });
  }, []);
  const onImage = (url: string) => {
    setImageUrl(url);
    saveImage(url);
    update({ backgrounds: { [theme.id]: "image" } });
  };
  const onReset = () => {
    clearOverrides();
    setOverrides({});
  };

  return (
    <>
      <div className="stage" onClick={goFullscreen}>
        <BackgroundLayer id={settings.background} palette={theme.palette} reducedMotion={reducedMotion} imageUrl={imageUrl} />
        <DecorLayer kind={settings.decorations && !reducedMotion ? theme.decor : null} palette={theme.palette} />
        <CardsLayer
          photos={feed.photos}
          loaded={feed.loaded}
          crossingSeconds={settings.crossingSeconds}
          newLabel={settings.newMarker ? theme.newLabel : null}
          headerRef={headerRef}
        />
        <Header ref={headerRef} title={config.title} qrUrl={config.qr_url} theme={theme} />
        {!feed.online && <div className="offline-dot" role="status" aria-label="Offline: showing cached photos" />}
      </div>

      <button className="gear" aria-label="Open settings" aria-expanded={drawerOpen} onClick={toggleDrawer}>⚙</button>
      <div className="hint" style={{ opacity: hint ? 1 : 0 }}>Press S for settings · F for fullscreen</div>
      <SettingsDrawer
        open={drawerOpen}
        settings={settings}
        onClose={closeDrawer}
        onChange={update}
        onImage={onImage}
        onReset={onReset}
        photoCount={feed.photos.length}
      />
    </>
  );
}
