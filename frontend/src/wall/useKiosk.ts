import { useEffect } from "react";

const IDLE_CURSOR_MS = 3000;

export function goFullscreen(): void {
  const el = document.documentElement;
  if (document.fullscreenElement || !el.requestFullscreen) return;
  el.requestFullscreen().catch(() => {});
}

const NON_TEXT_INPUTS = new Set(["radio", "checkbox", "range", "button", "submit", "reset", "file", "color"]);

/** Keys typed into a text field are text, not shortcuts. Radios, sliders and checkboxes don't count. */
function typingIn(target: EventTarget | null): boolean {
  if (target instanceof HTMLInputElement) return !NON_TEXT_INPUTS.has(target.type);
  return target instanceof HTMLTextAreaElement || (target instanceof HTMLElement && target.isContentEditable);
}

interface KioskHandlers {
  toggleDrawer(): void;
  closeDrawer(): void;
}

/** F = fullscreen, S = settings, Esc = close; screen wake lock; cursor hides after 3 s idle. */
export function useKiosk({ toggleDrawer, closeDrawer }: KioskHandlers): void {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") return closeDrawer();
      if (typingIn(e.target)) return;
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const k = e.key.toLowerCase();
      if (k === "s") toggleDrawer();
      else if (k === "f") goFullscreen();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [toggleDrawer, closeDrawer]);

  useEffect(() => {
    let lock: WakeLockSentinel | null = null;
    const request = async () => {
      try {
        lock = (await navigator.wakeLock?.request("screen")) ?? null;
      } catch {
        /* not allowed here; fine */
      }
    };
    const onVisible = () => {
      if (document.visibilityState === "visible") void request();
    };
    void request();
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      document.removeEventListener("visibilitychange", onVisible);
      void lock?.release().catch(() => {});
    };
  }, []);

  useEffect(() => {
    let timer = 0;
    const wake = () => {
      document.body.classList.remove("cursor-hidden");
      window.clearTimeout(timer);
      timer = window.setTimeout(() => document.body.classList.add("cursor-hidden"), IDLE_CURSOR_MS);
    };
    wake();
    window.addEventListener("mousemove", wake);
    window.addEventListener("mousedown", wake);
    return () => {
      window.clearTimeout(timer);
      window.removeEventListener("mousemove", wake);
      window.removeEventListener("mousedown", wake);
      document.body.classList.remove("cursor-hidden");
    };
  }, []);
}
