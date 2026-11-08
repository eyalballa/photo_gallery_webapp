// Dev-only fake backend (`/?mock`): sample photos as SVG data URLs, plus a "guest upload" every 40 s.
import type { ConfigResult, LoginResult, PublicConfig, PhotoOut, PhotosResponse, WallClient } from "./client";

const COLORS = ["#ff5d73", "#ffc145", "#4cc9f0", "#7ae582", "#b388ff", "#e3c193", "#c97b84"];

function samplePhoto(n: number): PhotoOut {
  const landscape = n % 3 !== 1;
  const [w, h] = landscape ? [1600, 1200] : [1200, 1500];
  const a = COLORS[n % COLORS.length] ?? "#888";
  const b = COLORS[(n + 3) % COLORS.length] ?? "#444";
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}">
    <defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="${a}"/><stop offset="1" stop-color="${b}"/></linearGradient></defs>
    <rect width="${w}" height="${h}" fill="url(#g)"/>
    <circle cx="${w / 2}" cy="${h / 2 - 60}" r="${Math.min(w, h) / 5}" fill="rgba(255,255,255,.35)"/>
    <text x="50%" y="${h - 160}" font-family="sans-serif" font-size="180" font-weight="700" text-anchor="middle" fill="#fff">#${n}</text>
  </svg>`;
  return {
    id: `mock-${n}`, w, h, aged: n % 5 === 0, first_seen: new Date().toISOString(), version: 1,
    url: `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`,
  };
}

export class MockWallClient implements WallClient {
  private readonly started = Date.now();

  async login(): Promise<LoginResult> {
    return "ok";
  }

  async publicConfig(): Promise<PublicConfig> {
    return { login_title: "Photo wall" };
  }

  async config(): Promise<ConfigResult> {
    return {
      kind: "ok",
      config: {
        title: "Happy 8th Birthday John!", qr_url: "https://photos.app.goo.gl/example", theme: "kids", background: null,
        decorations: true, crossing_seconds: 24, new_marker: true, effect_labels: {},
      },
    };
  }

  /** Photos 1–12 exist at start; one more arrives every 40 s. Stateless, like the real API. */
  async photos(since: string | null): Promise<PhotosResponse> {
    const now = Date.now();
    const arrived = (n: number) => this.started + Math.max(0, n - 12) * 40_000;
    const from = since ? Date.parse(since) : -Infinity;
    const total = 12 + Math.floor((now - this.started) / 40_000);
    const photos = Array.from({ length: total }, (_, i) => i + 1)
      .filter((n) => arrived(n) > from)
      .map(samplePhoto);
    return { photos, removed: [], server_time: new Date(now).toISOString() };
  }
}
