import { useCallback, useEffect, useState, type FormEvent } from "react";
import type { WallClient, WallConfig } from "./api/client";
import { ensureFonts } from "./lib/fonts";
import { kids } from "./themes/kids";
import { Wall } from "./wall/Wall";

type Gate =
  | { kind: "loading" }
  | { kind: "locked"; error: string | null }
  | { kind: "unreachable" }
  | { kind: "open"; config: WallConfig };

const RETRY_MS = 5000;
const DEFAULT_LOGIN_TITLE = "Photo wall";
const MEDIA_CACHE = "wall-media-v1"; // the service worker's photo cache (sw.ts)

/** No valid session: drop cached photos, so they don't outlive access on a computer we don't control. */
function forgetCachedPhotos(): void {
  if ("caches" in window) void caches.delete(MEDIA_CACHE).catch(() => {});
}

/** Shows the passcode screen while /api/config answers 401; otherwise goes straight to the wall. */
export function PasscodeGate({ client }: { client: WallClient }) {
  const [gate, setGate] = useState<Gate>({ kind: "loading" });

  const check = useCallback(async () => {
    try {
      const res = await client.config();
      if (res.kind === "ok") {
        setGate({ kind: "open", config: res.config });
      } else {
        forgetCachedPhotos();
        setGate({ kind: "locked", error: null });
      }
    } catch {
      setGate({ kind: "unreachable" });
    }
  }, [client]);

  useEffect(() => {
    void check();
  }, [check]);

  useEffect(() => {
    if (gate.kind !== "unreachable") return;
    const t = window.setTimeout(() => void check(), RETRY_MS);
    return () => window.clearTimeout(t);
  }, [gate, check]);

  if (gate.kind === "open") return <Wall client={client} config={gate.config} onLocked={check} />;
  return <GateScreen gate={gate} client={client} onUnlocked={check} onError={(error) => setGate({ kind: "locked", error })} />;
}

/** `login_title` from config.yaml; the default until it loads, or if the server can't be reached. */
function useLoginTitle(client: WallClient): string {
  const [title, setTitle] = useState(DEFAULT_LOGIN_TITLE);
  useEffect(() => {
    client.publicConfig().then((c) => setTitle(c.login_title), () => undefined);
  }, [client]);
  useEffect(() => {
    document.title = title;
  }, [title]);
  return title;
}

interface ScreenProps {
  gate: Exclude<Gate, { kind: "open" }>;
  client: WallClient;
  onUnlocked(): void;
  onError(message: string): void;
}

function GateScreen({ gate, client, onUnlocked, onError }: ScreenProps) {
  const [passcode, setPasscode] = useState("");
  const [busy, setBusy] = useState(false);
  const title = useLoginTitle(client);
  useEffect(() => ensureFonts(kids.fonts), []);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      const result = await client.login(passcode);
      if (result === "ok") onUnlocked();
      else if (result === "rate_limited") onError("Too many tries. Wait a minute, then try again.");
      else onError("That passcode didn't work. Try again.");
    } catch {
      onError("Can't reach the server. Try again in a moment.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="gate">
      {gate.kind === "loading" && <p className="gate-note">Loading…</p>}
      {gate.kind === "unreachable" && <p className="gate-note">Can't reach the server. Retrying…</p>}
      {gate.kind === "locked" && (
        <form className="gate-card" onSubmit={submit}>
          <h1>{title}</h1>
          <label htmlFor="passcode">Passcode</label>
          <input id="passcode" type="password" autoFocus autoComplete="current-password" value={passcode}
            onChange={(e) => setPasscode(e.target.value)} />
          {gate.error && <p className="gate-error" role="alert">{gate.error}</p>}
          <button className="btn" type="submit" disabled={busy || passcode.length === 0}>Open the wall</button>
        </form>
      )}
    </main>
  );
}
