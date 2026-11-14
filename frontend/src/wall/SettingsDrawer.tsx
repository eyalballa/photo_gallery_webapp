import type { ChangeEvent } from "react";
import type { WallClient } from "../api/client";
import { backgroundsFor } from "../backgrounds";
import { getTheme, THEMES } from "../themes";
import type { SettingsOverrides, WallSettings } from "../types";
import { EffectsSection } from "./EffectsSection";
import { goFullscreen } from "./useKiosk";

interface Props {
  client: WallClient;
  open: boolean;
  settings: WallSettings;
  onClose(): void;
  onChange(patch: SettingsOverrides): void;
  onImage(dataUrl: string): void;
  onReset(): void;
  photoCount: number;
}

interface Option {
  id: string;
  label: string;
  swatch: string;
}

function Options({ name, options, value, onPick }: { name: string; options: Option[]; value: string; onPick(id: string): void }) {
  return (
    <div className="opts">
      {options.map((o) => (
        <label className="opt" key={o.id}>
          <input type="radio" name={name} value={o.id} checked={o.id === value} onChange={() => onPick(o.id)} />
          <span>
            <i style={{ background: o.swatch }} />
            {o.label}
          </span>
        </label>
      ))}
    </div>
  );
}

/** S opens it. Changes are saved in this browser, on top of the config file's defaults. */
export function SettingsDrawer({ client, open, settings, onClose, onChange, onImage, onReset, photoCount }: Props) {
  const theme = getTheme(settings.theme);
  const onFile = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      if (typeof reader.result === "string") onImage(reader.result);
    };
    reader.readAsDataURL(file);
  };

  return (
    <aside className={open ? "panel open" : "panel"} aria-label="Wall settings" aria-hidden={!open} inert={!open}>
      <header>
        <h2>Wall settings</h2>
        <button className="btn ghost" onClick={onClose}>Close</button>
      </header>
      <p className="note">Saved in this browser, on top of the config file (except photo effects). Press S to toggle, F for fullscreen.</p>

      <section>
        <h3>Theme</h3>
        <Options name="theme" options={[...THEMES]} value={settings.theme} onPick={(id) => onChange({ theme: id })} />
      </section>

      <section>
        <h3>Background</h3>
        <Options
          name="bg"
          options={backgroundsFor(theme.id)}
          value={settings.background}
          onPick={(id) => onChange({ backgrounds: { [theme.id]: id } })}
        />
        <label className="file-label">
          Use your own image
          <input type="file" accept="image/*" onChange={onFile} />
        </label>
      </section>

      <section>
        <h3>Wall</h3>
        <div className="row">
          <label htmlFor="speed">Seconds to cross</label>
          <input id="speed" type="range" min={8} max={60} step={1} value={settings.crossingSeconds}
            onChange={(e) => onChange({ crossingSeconds: Number(e.target.value) })} />
          <output>{settings.crossingSeconds} s</output>
        </div>
        <div className="row">
          <label htmlFor="decor-on">
            Decorations <small>{theme.decor ? `(${theme.decor})` : "(none in this theme)"}</small>
          </label>
          <input id="decor-on" type="checkbox" disabled={!theme.decor} checked={settings.decorations}
            onChange={(e) => onChange({ decorations: e.target.checked })} />
        </div>
      </section>

      <EffectsSection client={client} open={open} />

      <section>
        <div className="btns">
          <button className="btn" onClick={goFullscreen}>Fullscreen</button>
          <button className="btn ghost" onClick={onReset}>Reset to config</button>
        </div>
        <p className="stats">{photoCount} photos on the wall</p>
      </section>
    </aside>
  );
}
