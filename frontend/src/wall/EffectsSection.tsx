import { useEffect, useState } from "react";
import type { EffectsSettings, WallClient } from "../api/client";

type EffectRow = EffectsSettings["effects"][number];

/** Effect switches in the settings drawer. Unlike the rest of the drawer these are saved on the server, so they
 * apply to every screen and to photos processed from now on; "Re-pick" applies them to photos already on the wall. */
export function EffectsSection({ client, open }: { client: WallClient; open: boolean }) {
  const [state, setState] = useState<EffectsSettings | null>(null);
  const [honoree, setHonoree] = useState("");
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    let live = true;
    client.effects().then(
      (s) => {
        if (!live) return;
        setState(s);
        setHonoree(s.honoree ?? "");
      },
      () => live && setMessage("Couldn't load the effects."),
    );
    return () => {
      live = false;
    };
  }, [client, open]);

  if (!state) return message ? <section><h3>Photo effects</h3><p className="note">{message}</p></section> : null;

  const save = async (off: string[], name: string) => {
    try {
      const next = await client.setEffects({ off, honoree: name });
      setState(next);
      setMessage("Saved. New photos use these; Re-pick updates the ones already up.");
    } catch {
      setMessage("Couldn't save. Try again.");
    }
  };
  const offIds = state.effects.filter((e) => !e.on).map((e) => e.id);
  const toggle = (e: EffectRow, on: boolean) =>
    save(on ? offIds.filter((id) => id !== e.id) : [...offIds, e.id], honoree);
  const saveHonoree = () => {
    if (honoree.trim() !== (state.honoree ?? "")) void save(offIds, honoree);
  };
  const reroll = async () => {
    if (!window.confirm("Re-pick the effect for every photo on the wall?")) return;
    try {
      const { queued } = await client.rerollEffects();
      setMessage(`Re-picking ${queued} photos. Each one changes the next time it crosses the wall.`);
    } catch {
      setMessage("Couldn't start the re-pick. Try again.");
    }
  };

  const group = (kind: EffectRow["kind"], title: string) => (
    <>
      <p className="note sub">{title}</p>
      {state.effects.filter((e) => e.kind === kind).map((e) => (
        <div className="row" key={e.id}>
          <label htmlFor={`fx-${e.id}`}>{e.label}</label>
          <input id={`fx-${e.id}`} type="checkbox" checked={e.on} onChange={(ev) => void toggle(e, ev.target.checked)} />
        </div>
      ))}
    </>
  );

  return (
    <section>
      <h3>Photo effects</h3>
      <p className="note">Saved on the server for every screen. Each photo with faces gets one of the effects that are on.</p>
      {group("face", "On faces")}
      {group("photo", "Whole photo")}
      <div className="row">
        <label htmlFor="honoree">Name on the cake</label>
        <input id="honoree" type="text" maxLength={60} placeholder="e.g. John" value={honoree}
          onChange={(e) => setHonoree(e.target.value)} onBlur={saveHonoree}
          onKeyDown={(e) => e.key === "Enter" && e.currentTarget.blur()} />
      </div>
      <div className="btns">
        <button className="btn ghost" onClick={() => void reroll()}>Re-pick effects for all photos</button>
      </div>
      {message && <p className="stats" role="status">{message}</p>}
    </section>
  );
}
