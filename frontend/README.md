# Photo wall — frontend

Vite + React + TypeScript (strict). The spec is `docs/DESIGN.md` §6; the visual reference is `mockup/wall-sample.html`.

## Setup

```sh
pnpm install
pnpm gen:api      # regenerate src/api/schema.d.ts from openapi.json (never edit it by hand)
```

To refresh `openapi.json` itself, export it from the backend (FastAPI's `/openapi.json`) and then run `pnpm gen:api`.

## Develop

```sh
pnpm dev          # http://localhost:5173, proxies /api and /media to http://localhost:8000
```

No backend running? Open `http://localhost:5173/?mock` to use a built-in fake client (dev only). It starts with 12 sample photos and adds a new one every 40 s.

Keys on the wall: **S** settings drawer, **F** (or a click) fullscreen, **Esc** close drawer.

## Test and build

```sh
pnpm test         # vitest: scheduler, poll merging, settings
pnpm build        # tsc -b (strict) + vite build → dist/
```

`dist/` has `index.html`, `assets/*` and `sw.js`, the service worker that caches `/media/*` cache-first. It has to be served from `/sw.js` (the backend's SPA fallback serves real files under `dist/`), and it's registered only in production builds.

## Layout

- `src/api/`: `schema.d.ts` (generated), `client.ts` (the `WallClient` interface plus the HTTP implementation), `mockClient.ts` (dev fake)
- `src/wall/scheduler.ts`: queue order and spawn rules. Pure: time and RNG are passed in.
- `src/wall/feed.ts`: polling and merging (`since` = the last `server_time`)
- `src/wall/`: `Wall.tsx`, `CardsLayer.tsx`, `DriftingCard.tsx`, `Header.tsx`, `SettingsDrawer.tsx`, hooks
- `src/themes/`, `src/backgrounds/`, `src/decor/`: plug-ins. Adding one is one file plus one line in its `index.ts`.
- `src/settings.ts`: config defaults plus localStorage overrides
