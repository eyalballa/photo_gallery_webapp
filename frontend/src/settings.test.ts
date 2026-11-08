import { describe, expect, it } from "vitest";
import type { WallConfig } from "./api/client";
import { parseOverrides, resolveSettings } from "./settings";

const config: WallConfig = {
  title: "Happy 8th Birthday John!", qr_url: "https://photos.app.goo.gl/x", theme: "kids", background: "space",
  decorations: true, crossing_seconds: 24, new_marker: true, effect_labels: {},
};

describe("resolveSettings", () => {
  it("uses config defaults when nothing is overridden", () => {
    expect(resolveSettings(config, {}, false)).toEqual({
      theme: "kids", background: "space", crossingSeconds: 24, decorations: true, newMarker: true,
    });
  });

  it("applies local overrides on top, clamped to the config's ranges", () => {
    const s = resolveSettings(config, { crossingSeconds: 5, decorations: false }, false);
    expect([s.crossingSeconds, s.decorations]).toEqual([8, false]);
  });

  it("falls back to the theme default for a background the theme doesn't allow", () => {
    expect(resolveSettings(config, { theme: "grown" }, false).background).toBe("velvet");
    expect(resolveSettings(config, { backgrounds: { kids: "champagne" } }, false).background).toBe("party-night");
  });

  it("only uses the image background when an image is set", () => {
    expect(resolveSettings(config, { backgrounds: { kids: "image" } }, false).background).toBe("party-night");
    expect(resolveSettings(config, { backgrounds: { kids: "image" } }, true).background).toBe("image");
  });
});

describe("parseOverrides", () => {
  it("keeps well-typed fields and drops the rest", () => {
    expect(parseOverrides('{"theme":"grown","maxOnScreen":"3","decorations":false}')).toEqual({ theme: "grown", decorations: false });
    expect(parseOverrides("not json")).toEqual({});
  });
});
