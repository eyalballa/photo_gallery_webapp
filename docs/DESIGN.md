# Birthday Photo Wall: Design & Plan

A web page projected on a wall at a birthday party. Guests add photos to a Google Photos
shared album; within a couple of minutes each photo floats across the wall, right to left,
in a polaroid frame. Photos with people get a fun effect (glasses, mustache, party hat or
vintage). The wall runs in a browser on a computer we don't control and is protected by a
passcode.

Visual reference: [`mockup/wall-sample.html`](../mockup/wall-sample.html) (open in a browser, press **S** for settings).

---

## 1. Goals and non-goals

**Goals**
- Live: a photo added to the album appears on the wall within about 2 minutes.
- Every uploader gets screen time: new photos jump the queue, then least-shown first.
- Big, readable photos: 3–4 on screen, each about a quarter of the screen.
- Pluggable: themes, backgrounds, effects and the photo source are each a plug-in behind a small interface.
- Nothing to install on the projector computer: a URL, a passcode, fullscreen.
- Keeps running through short Wi-Fi drops.

**Non-goals**
- A custom upload page (guests use the Google Photos app).
- Uploader names or captions on the wall.
- An admin UI for moderation (the album is the moderation tool: delete a photo there).
- Multi-event or multi-user support.

## 2. Decisions

| Topic | Decision |
|---|---|
| Photo source | Google Photos **shared album**, read through **`ShareLinkSource`** (the album's public share link). M0 found that the Ambient API requires Google Photos partner-program access (`PERMISSION_DENIED` on `devices.create`); see [M0.md](M0.md). |
| Fallback source | `AmbientSource`, if partner access is ever granted. It's already written and sits behind the same `PhotoSource` interface. |
| Sync cadence | Fetch the share link every **90 s**. Each fetch returns the whole album, so new photos and deletions come from the same call. The spike measured about 6 s from upload to visible (see [M0.md](M0.md)). |
| Moderation | Remove a photo from the album and it leaves the wall within about 5 min. |
| Ambient filtering | Accept Google's default content filtering. De-duplicate by media item id. Skip videos. |
| Face effects | Run **once per photo on the backend** (MediaPipe Face Landmarker + Pillow/OpenCV) and cache the result. |
| Effect choice | Random, weighted, fixed per photo (seeded by media id). Default weights: glasses / mustache / party hat / vintage 25 each; circus glasses 15; big eyes, pop art, pencil sketch, wanted poster, confetti and cake frame 10 each. Effects can be switched on and off from the settings drawer. Every face over about 60 px gets the same effect type. Photos without faces show unedited. |
| Display | 3–4 polaroids max, single file, one shared speed (~24 s to cross), alternating high and low, gentle bob and tilt, no captions. "NEW" marker on a photo's first appearance. |
| Order | Newest first, then least shown, then random. |
| Themes | **Kids party**, **Young adult** and **Roses & gold** (after a bat mitzvah invitation: blush, gold frames, roses). They differ in fonts, palette, background and decorations (see §6.3). |
| Header | Title from config ("Happy 8th Birthday John!") plus a small QR code linking to the album's join link. |
| Access | Passcode screen, then a signed HttpOnly cookie (30 days). Photos are served only to authenticated sessions. |
| Offline | A service worker caches processed photos, so the wall keeps cycling during network drops. |
| Stack | Backend: Python 3.12, FastAPI, SQLite. Frontend: Vite + React + TypeScript. Animation uses the Web Animations API / CSS transforms, not React re-renders. |
| Hosting | One Docker Compose stack on a small Linux server, exposed through **Tailscale Funnel** (`https://party.<tailnet>.ts.net`). |
| Scale | About 30 guests, a few hundred photos, 6 hours or less. |
| Data retention | Processed photos live on a local volume and are wiped after the event (`wipe` command). |

## 3. Architecture

```
 Guests' phones                     Linux server (docker compose)                         Projector computer
┌──────────────┐  upload   ┌─────────────────────────────────────────────────────┐      ┌───────────────────┐
│ Google Photos│ ───────▶  │ ┌──────────────┐   ┌────────────────┐   ┌──────────┐ │      │ Browser (kiosk)   │
│ shared album │           │ │ Sync worker  │──▶│ Process worker │──▶│  /data   │ │      │  React wall app   │
└──────┬───────┘           │ │ PhotoSource  │   │ faces+effects  │   │ jpg+sqlite│ │      │  service worker   │
       │ Ambient API       │ └──────┬───────┘   └────────────────┘   └────┬─────┘ │      └─────────▲─────────┘
       └──────────────────▶│        │ refresh token                       │       │                │
                           │ ┌──────▼──────────────────────────────────────▼────┐ │   HTTPS        │
                           │ │ FastAPI: /api/login /api/config /api/photos       │◀┼───(Tailscale───┘
                           │ │          /media/{id}.jpg  + static React build    │ │    Funnel)
                           │ └───────────────────────────────────────────────────┘ │
                           │ tailscale sidecar (Funnel :443 → app:8000)            │
                           └─────────────────────────────────────────────────────┘
```

A single Python process runs FastAPI plus two asyncio background tasks (sync and process).
That's enough at this scale; face detection runs in a thread pool so it doesn't block the API.

### 3.1 One core, two front doors

All behaviour lives in a **service layer** (`WallService`). It takes pydantic models in and returns pydantic models out. The web API and the CLI are both thin adapters over it, with no logic of their own:

```
            ┌──────────── FastAPI routes (api.py) ────────────┐
 browser ──▶│ parse request → service call → response_model   │
            └───────────────────────┬─────────────────────────┘
                                    ▼
                         WallService (service.py)   ◀── Deps: source, store, clock, detector, config
                                    ▲
            ┌───────────────────────┴─────────────────────────┐
 terminal ─▶│ Typer commands (cli.py) → service call → print   │
            └─────────────────────────────────────────────────┘
```

```python
class WallService:
    def __init__(self, deps: Deps): ...
    def get_config(self) -> WallConfig: ...
    def list_photos(self, since: datetime | None) -> PhotosResponse: ...
    def get_media(self, photo_id: str) -> MediaFile: ...
    def check_passcode(self, req: LoginRequest) -> bool: ...
    async def sync_once(self) -> SyncReport: ...                 # new / removed counts
    async def process_pending(self, limit: int | None) -> ProcessReport: ...
    async def reroll(self, photo_id: str | None) -> ProcessReport: ...   # re-processes, so async
    def status(self) -> StatusReport: ...
    def wipe(self) -> None: ...
```

So the server can be run and tested standalone, with no browser and no Google:
- `wall sync` runs one sync pass now. `wall process` processes whatever is pending. `wall photos [--since]` prints the same `PhotosResponse` the browser would get.
- `wall --source fake:./samples process` uses a folder of local images as the photo source, to check effects without Google.
- `wall --remote https://party.<tailnet>.ts.net --passcode … photos` sends the same commands over HTTP to a running server, through a typed `httpx` client that shares `schemas.py`. It's a smoke test for the deployed box.
- Output is human-readable by default, or `--json` to print the pydantic model as JSON (handy for scripts and diffing).

## 4. Backend

### 4.1 Photo source plug-in

```python
class PhotoSource(Protocol):
    id: str
    async def list_items(self) -> SourceListing: ...   # the whole album, every 90 s
    async def download(self, item: SourceItem, max_px: int) -> bytes: ...

class SourceItem(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: str              # stable media id
    created: datetime    # when it was added to the album
    width: int
    height: int
    url: str             # source-specific locator handed back to download()

class SourceListing(BaseModel):
    items: list[SourceItem]
    complete: bool       # False if the listing may be missing items; sync then skips removals
```

**`ShareLinkSource`** (primary, `wall/sources/sharelink.py`; findings in [M0.md](M0.md))
- Resolves the short link with a non-browser User-Agent (HTTP 302 to `photos.google.com/share/…?key=…`), then fetches that page with a browser User-Agent and parses the JSON in its `ds:1` data block. No login.
- Every fetch returns the whole album, so new photos and deletions come from the same call.
- Videos (items carrying key `"76647426"`) are skipped.
- `complete` is False when the page has a next-page token or its item count differs from the album's total (`data[3][21]`). Large albums may page; until that's seen, we only guard against it.
- Downloads use `<url>=w1600-h1600`, which comes back as JPEG, so HEIC files never reach us.

**`FakePhotoSource`** (`--source fake:<dir>`): a folder of local images. Used by tests and offline runs.

**Ambient API**: rejected. It needs Google Photos partner-program access (M0); the probe code was removed with the Google Cloud project.

### 4.2 Sync worker

```
every 90 s:  listing = source.list_items()
             new ids     → download now (6 at a time) → /data/originals/{id}.jpg → status=pending
             missing ids → status=removed   (only if listing.complete)
             then process pending photos
```
A failed download leaves the item unknown, so it's retried on the next pass. A photo deleted and
re-added comes back as pending. The last sync time and error are kept for `wall status`.

### 4.3 Processing worker and the effect plug-in

Pipeline per photo: **load → EXIF-rotate → resize (1600 px long side) → detect faces → pick
effect → apply → save `/data/processed/{id}.jpg` → status=ready**.

```python
class Point(BaseModel):
    x: float
    y: float

class Rect(BaseModel):
    x: float
    y: float
    w: float
    h: float

class Landmarks(BaseModel):
    left_eye: Point
    right_eye: Point
    nose_tip: Point
    mouth_center: Point
    forehead: Point
    chin: Point

class Face(BaseModel):
    box: Rect                 # pixels
    landmarks: Landmarks
    roll: float               # radians, from the eye line
    yaw: float                # nose offset from the eye midpoint, in eye distances (0 = frontal)
    size: float               # inter-ocular distance, the unit all effects scale by

class EffectResult(BaseModel):
    variant: str | None       # e.g. "heart" glasses
    aged_paper: bool = False  # the frontend uses a yellowed polaroid

class Effect(Protocol):
    id: str
    label: str
    weight: float             # default weight, can be overridden by config
    accessory: bool           # draws on faces, so skipped for turned faces
    def apply(self, img: Image, faces: list[Face], rng: Random) -> EffectResult: ...

EFFECTS: dict[str, Effect] = {}
def register(effect: Effect) -> Effect: ...   # used as a decorator in effects/*.py
```

- **Adding an effect** means dropping a file in `backend/wall/effects/` that defines a class with `@register`. Config can set `weights: {party_hat: 0}` to turn one off; `python -m wall effects` lists the live effects with their current weights, and an unknown id in `weights` is warned about at startup.
- **Switching effects from the wall:** the settings drawer's *Photo effects* section has an on/off box per effect and the cake-frame name. They're saved in the DB `meta` table (key `effects`, because `config.yaml` is mounted read-only), on top of config.yaml: an effect switched off gets weight 0, one switched on keeps its config weight (or its own default when the config had it at 0). They apply to photos processed from then on; *Re-pick effects for all photos* sends every ready photo back to processing with a new salt. `wipe` clears them.
- **Face detection:** MediaPipe Face Landmarker (`face_landmarker.task`, 478 points with irises), up to 10 faces per pass. Its detector is short-range and missed most faces in group shots (8 of ~105 on the golden set), so `wall/faces.py` also scans overlapping 2×2 and 3×3 tiles (25% overlap) and merges the results: duplicates are dropped when eye positions are within half an eye distance, and faces touching an inner tile edge are discarded. That found 105 faces, at about 0.1 s per photo. Faces whose box is narrower than `min_face_px` (60 px) are ignored. If no qualifying faces are found, the photo gets no effect.
- **Turned faces:** a yaw proxy (nose offset from the eye midpoint along the eye line, in eye distances) above `max_yaw` (0.35) skips accessories for that face; if no face is frontal, only whole-photo (non-accessory) effects are eligible.
- **Choosing an effect:** `rng = Random(sha256(media_id)[:8] ^ reroll_salt)` (Python's `hash()` changes per process), then a weighted pick among enabled effects, then the effect's own variant pick. The choice is stored in the DB, so restarts don't change it.
- **Effects:**
  - **Accessories** (glasses, mustache, party hat) are SVG assets in `backend/assets/<effect>/<variant>.svg`. They're rasterized with `resvg-py` (self-contained, no system cairo) at the needed size, rotated by `roll` and anchored to landmarks. Each asset's viewBox defines its anchor:
    - glasses: centre of the asset on the eye midpoint, width 2.4 × inter-ocular distance (lens centres at 0.29 / 0.71 of the width)
    - mustache: asset point (0.5, 0.3) at 30% of the way from nose tip to mouth, width 1.5 ×
    - hat: brim centre (0.5, 0.94) half an eye distance above the forehead landmark along the face's up vector, width 2.2 ×
    - circus glasses: oversized novelty glasses, eye midpoint on asset point (0.5, 100/260), width 4 × (the 400×260 assets put the eyes at x 150 / 250, with the lenses further out so the eyes look small inside them)
    - all of them were tuned on the golden set (`python -m wall.golden golden/input golden/output` renders every image with every effect, plus contact sheets)
  - **Big eyes** (accessory): a smooth magnifying warp centred on each iris (about 2–2.5× at the centre; radius 0.5 × inter-ocular distance along the eye line so the two bulges just meet, 1.25× that vertically), plus anime catch-lights. Variants: cute, huge.
  - **Vintage** is a pixel transform (sepia matrix, fade, grain, vignette, a few scratches) and sets `aged_paper=True`.
  - **Pop art:** four copies in a 2×2 grid, each cut to three flat tones (thresholds taken from the face region) and recoloured with clashing colours. Variants: warhol, candy, electric.
  - **Pencil sketch:** greyscale colour-dodge sketch with cross-hatching in the shadows, on paper grain; `aged_paper=True`. Variants: graphite, sepia, charcoal.
  - **Wanted poster:** the photo sepia-toned and cropped around the faces on a parchment poster with WANTED, a kid-friendly charge and a made-up reward (the variant); `aged_paper=True`. Text uses Pillow's built-in font (no system fonts in the image), so it's ASCII only.
  - **Confetti:** a few hundred tumbling pieces (strips, dots, stars, streamers) with shadows, thinned out over face boxes. Variants: rainbow, gold, pastel.
  - **Cake frame:** tiled frosting drips along the top, a cake band with candles and "Happy Birthday, {honoree}!" along the bottom (SVG tiles in `backend/assets/cake_frame/`). The photo shrinks a little if the frame would cover a face. Variants: strawberry, chocolate, vanilla, blueberry.
  - Asset variants at launch: glasses = round, heart, star, aviator; circus glasses = clown, groucho (nose, eyebrows and mustache), stars, hypno; mustache = handlebar, walrus, chevron; hat = striped cone in palette colors.
- **Failures:** an effect error falls back to the unedited photo, still status ready, and the error is logged.

### 4.4 Storage (SQLite, `/data/wall.db`)

```sql
photos(
  id TEXT PRIMARY KEY, source TEXT, url TEXT, created_at TEXT, first_seen_at TEXT,
  removed_at TEXT, processed_at TEXT,   -- drive the `since` queries of /api/photos
  status TEXT CHECK(status IN ('pending','ready','failed','removed')),
  width INT, height INT, faces INT,
  effect TEXT, variant TEXT, aged_paper INT,
  reroll_salt INT DEFAULT 0,
  version INT DEFAULT 1,         -- bumped on re-process, busts browser cache
  error TEXT
)
meta(key TEXT PRIMARY KEY, value TEXT)   -- last_sync, last_sync_error
```

### 4.5 HTTP API

| Route | Auth | Purpose |
|---|---|---|
| `POST /api/login` `{passcode}` | none | 204 + the `wall_session` cookie, 401 for a wrong passcode, 429 (`Retry-After: 60`) past 5 attempts/min per IP. |
| `GET /api/public` | none | `login_title` only: what the passcode screen shows. Nothing private. |
| `GET /api/config` | cookie | Title, theme, background, timing, QR link, effect labels. |
| `GET /api/photos?since=<iso>` | cookie | Photos that are ready: `id, w, h, aged, firstSeen, version, url`. Includes `removed` ids since the given time. |
| `GET /api/effects` | cookie | Each effect's id, label, kind (face / photo) and on/off, plus the cake-frame name. |
| `PUT /api/effects` `{off, honoree}` | cookie | Saves the switches (422 for an unknown id); applies to photos processed from now on. |
| `POST /api/effects/reroll` | cookie | Sends every ready photo back to processing; returns `{queued}`. |
| `GET /media/{id}.jpg?v=` | cookie | Processed image, `Cache-Control: private, max-age=86400`. |
| `GET /*` | none | The React build. It shows the passcode screen until the session is valid. |

The frontend polls `/api/photos` every 15 s. No websockets; it's simpler and survives reconnects.

Every request and response body is a pydantic model in `wall/schemas.py`, for example:

```python
class LoginRequest(BaseModel):
    passcode: str

class PhotoOut(BaseModel):
    id: str
    w: int
    h: int
    aged: bool
    first_seen: datetime
    version: int
    url: str

class PhotosResponse(BaseModel):
    photos: list[PhotoOut]
    removed: list[str]
    server_time: datetime          # the client passes this back as `since`

class WallConfig(BaseModel):
    title: str
    qr_url: HttpUrl
    theme: Literal["kids", "grown", "roses"]
    background: str | None
    decorations: bool
    crossing_seconds: int = Field(ge=8, le=60)
    new_marker: bool
    effect_labels: dict[str, str]
```

Routes declare `response_model=`. The TypeScript types for these payloads are generated from FastAPI's OpenAPI schema (`openapi-typescript` → `frontend/src/api/schema.d.ts`), so the client and server can't drift apart.

### 4.6 CLI (`python -m wall …`, Typer)

Each command calls the same `WallService` method as the matching API route (§3.1). Global options: `--config`, `--source sharelink|fake:<dir>` (sharelink is the default), `--remote <url> --passcode <p>`, `--json`.

| Command | Service method | Matching route |
|---|---|---|
| `config` | `get_config` | `GET /api/config` |
| `photos [--since]` | `list_photos` | `GET /api/photos` |
| `media ID [-o file]` | `get_media` | `GET /media/{id}.jpg` |
| `login` | `check_passcode` | `POST /api/login` |
| `sync` | `sync_once` | (background task) |
| `process [--limit]` | `process_pending` | (background task) |
| `reroll [--id]` | `reroll` | none |
| `status` | `status` | none |
| `wipe` | `wipe` | none |
| `public-config` | `get_public_config` | `GET /api/public` |
| `openapi` | writes `frontend/openapi.json` for the generated TS types | none |
| `serve` | starts FastAPI and the background tasks | none |

`--remote` works only for commands that have a route. The others always run locally.

## 5. Configuration

`config.yaml` (mounted) plus `.env` for secrets. Both are loaded into pydantic models (`AppConfig`, and `AuthSettings` via `pydantic-settings`), so a bad config fails at startup with a clear message.

```yaml
event:
  title: "Happy 8th Birthday John!"         # header and tab, after login
  login_title: "Photo wall"                 # passcode screen: public, so no names
  qr_url: "https://photos.app.goo.gl/…"     # album join link shown in the corner
  album_url: "https://photos.app.goo.gl/…"  # the shared album link read by ShareLinkSource
display:
  theme: kids              # kids | grown | roses
  background: null         # null = theme default; or confetti, party-night, velvet, …
  decorations: true        # balloons
  crossing_seconds: 24
  new_marker: true
effects:
  weights: { glasses: 25, circus_glasses: 15, mustache: 25, party_hat: 25, big_eyes: 10, vintage: 25, pop_art: 10, sketch: 10,
             wanted: 10, confetti: 10, cake_frame: 10 }
  honoree: null             # name on the cake frame
  min_face_px: 60
  max_yaw: 0.35             # turned faces skip accessories
sync:
  every_s: 90
```

```
# .env
PASSCODE=…
SESSION_SECRET=…            # 32+ random bytes
COOKIE_SECURE=true          # false only for plain-http testing
TS_AUTHKEY=…                # tailscale sidecar: a pre-authorized key tagged tag:party
TS_EXTRA_ARGS=--advertise-tags=tag:party
```

## 6. Frontend

### 6.1 Structure

```
frontend/src/
  main.tsx, App.tsx            PasscodeGate → Wall
  api/schema.d.ts              generated from the backend OpenAPI schema (never hand-edited)
  api/client.ts                typed login / config / photos calls built on schema.d.ts
  types.ts                     client-only structs: WallPhoto, CardState, QueueEntry
  wall/
    Wall.tsx                   layers: Background, Decor, Cards, Header
    scheduler.ts               queue order + spawn rules (pure, unit-tested)
    DriftingCard.tsx           polaroid + WAAPI drift + CSS bob
    Header.tsx                 title renderer from theme + QR (generated with `qrcode`)
  themes/       index.ts, kids.ts, grown.ts, roses.ts
  backgrounds/  index.ts, partyNight.ts, confetti.ts, space.ts, sea.ts, velvet.ts, champagne.ts, film.ts, blush.ts, image.ts
  decor/        balloons.ts, petals.ts
  sw.ts                        hand-written service worker (~25 lines, no Workbox): cache-first for /media, served at /sw.js
```

### 6.2 Plug-in interfaces

```ts
interface Theme {
  id: string; label: string;
  tokens: Record<string, string>;            // CSS custom properties, applied on <body data-look>
  fonts: string[];                           // Google Fonts families to load
  palette: string[];                         // used by confetti, balloons, title letters
  defaultBackground: string;
  decor: "balloons" | null;
  newLabel: string; qrCaption: string;
  renderTitle(text: string): ReactNode;
  motion: { tilt: number; bob: number };     // multipliers
}

interface Background {
  id: string; label: string;
  themes: string[];                          // which themes may use it
  mount(host: HTMLElement, ctx: { palette: string[]; reducedMotion: boolean }): () => void;  // returns unmount
}
```
Adding a theme or background means one file plus one line in its `index.ts`. Canvas
backgrounds share a `canvasBackground({setup, frame})` helper (DPR capped at 1.5).

### 6.3 Themes

| | Kids party | Young adult | Roses & gold |
|---|---|---|---|
| Title font | Lilita One, one color per letter, gentle wave | Fraunces 800, one color, gold rule underneath | Secular One (Hebrew-capable): white letters, pink outline and offset shadow, dotted pink rule; right-to-left for a Hebrew title |
| UI font | Fredoka | Manrope | Assistant (Hebrew-capable) |
| Palette | coral, sun, sky, mint, grape | champagne, rose, cream, antique gold, plum | pink, blush, gold, white, sage on a light blush page |
| Frames | Polaroid, full tilt and bob | Polaroid, softer tilt and bob | White polaroid with a soft mauve shadow, gentlest tilt and bob |
| Backgrounds | Party night (default), Confetti, Outer space, Under the sea, Your image | Velvet (default), Confetti, Champagne, Film night, Your image | Blush & roses (default: watercolor washes, white circle, swaying gold polygon frames, rose bouquets), Confetti, Your image |
| Decorations | Balloons | Balloons (theme palette) | Falling rose petals |
| New marker | "NEW" starburst | "Just added" pill | "New" pink ribbon |

### 6.4 Scheduler rules (as in the mockup)

- **Size:** usable band = from below the header to 97% of the height. Image height ≈ 56% of the band (±5%), polaroid padding 4.5% on the sides and 20% at the bottom.
- **Motion:** one shared speed `v = (viewportW + 0.7·viewportH) / crossing_seconds`, so cards never catch up with each other. If the speed goes up (settings drawer, resize), a new card waits until it can't catch the last one before that one leaves.
- **Spawning:** a new card enters when the previous card has fully entered plus a gap drawn at random per card, between 2% and 12% of the width, so the spacing isn't monotonous. There's no maximum count: spacing alone decides, so the number of photos on screen follows the screen's width and the photos' shapes (more narrow portrait cards fit than wide landscape ones). A fixed `max_on_screen` was removed because it left holes when narrow cards needed more than the maximum to fill the screen.
- **Vertical position:** alternates between the top 25% and the bottom 25% of the band's slack.
- **Queue:** `isNew desc, shownCount asc, random`. `shownCount` is kept in memory, and `isNew` means it arrived after this browser session started and hasn't been shown yet (photos already in the album at startup aren't new). The picked next photo is kept across ticks while it still ranks first, and pre-decoded before its slot opens. Photos that are removed or currently on screen are excluded.
- **Startup:** cards are placed mid-flight, so the first frame is a full wall.
- **Loading:** images are pre-decoded (`img.decode()`) before a card enters, to avoid jank.
- **Reduced motion:** no bob, wave or balloons. The drift stays, since it's the core of the wall.

### 6.5 Kiosk behaviour

- Fullscreen on **F** or a click.
- Screen wake lock, requested and allowed to fail silently.
- The cursor hides after 3 s idle.
- **S** opens the settings drawer (theme, background, speed, max, decorations). Changes are saved in that browser's localStorage, on top of the config defaults, so the look can be adjusted on site without redeploying.
- If `/api/photos` fails, the wall keeps cycling cached photos and a small dot in the corner shows it's offline (hidden while healthy).

## 7. Security

- The passcode is compared in constant time. The session cookie is `HttpOnly; Secure; SameSite=Lax`, lasts 30 days, and holds `<expiry>.<HMAC-SHA256(expiry, SESSION_SECRET)>` (`wall/auth.py`): stateless, so it survives restarts while the secret stays the same. Without `SESSION_SECRET` a random one is used and sessions end on restart. The HMAC key includes the passcode, so changing `PASSCODE` ends every session. `serve` refuses to start without a `PASSCODE` of 8+ characters (and refuses the example value).
- Every `/api/*` and `/media/*` request requires the cookie. The React shell is public but contains no data.
- Login is rate-limited per IP (5/min) and in total (30/min), as sliding windows in memory, so rotating IPs can't brute-force the passcode. uvicorn trusts `X-Forwarded-For` only from 127.0.0.1, the Tailscale proxy.
- If the session expires mid-event, the wall keeps cycling its cached photos and shows the offline dot rather than going blank; a reload shows the passcode screen, which also deletes the service worker's photo cache.
- Every response carries a CSP (self only, plus Google Fonts; `frame-ancestors 'none'`), `nosniff` and `Referrer-Policy: no-referrer`. FastAPI's `/docs` and `/openapi.json` are off; `wall openapi` exports the schema.
- The app container gets only `PASSCODE`, `SESSION_SECRET` and `COOKIE_SECURE` from `.env`; `TS_AUTHKEY` goes only to the tailscale container. `--remote` reads the passcode from `WALL_PASSCODE` so it stays out of the process list.
- The browser never sees Google URLs: photos are downloaded by the server and served from `/media`. The album link lives only in `config.yaml` (and the QR, if `qr_url` is the same link). httpx request logging is silenced because it would print signed photo URLs, and sync errors are logged and stored without their URLs. The server downloads only from `https://*.googleusercontent.com`, and media ids must be `[A-Za-z0-9_-]` since they become file names.
- The Funnel URL is public but unguessable-ish; the passcode is the real gate.
- Network: the app listens on `127.0.0.1:8000` only, inside the tailscale container's namespace, so Serve/Funnel on 443 is the one way in (not the Docker bridge, not other tailnet devices). Nothing is published on the host. The node is tagged `tag:party` with no outbound ACL rules, so a compromised app can't reach the rest of the tailnet. Whoever can log in to the server has everything (`.env`, photos, `ts-state/`), so it takes SSH keys only, behind a firewall.
- `SESSION_SECRET`, when set, must be 32+ characters, because cookie checks aren't rate-limited.
- Wipe the data after the event.

## 8. Deployment

Step by step in [DEPLOY.md](DEPLOY.md). Files at the repo root:

- `Dockerfile` (multi-stage): `node:24-slim` builds the frontend; `python:3.12-slim` plus `uv sync --frozen` runs it, with the MediaPipe model baked in. Slim needs `libgl1 libegl1 libgles2 libglib2.0-0 libxcb1`: MediaPipe and the full OpenCV it pulls in load them even when headless.
- `docker-compose.yml`: `app` (mounts `./data` and `./config.yaml` at `/app/backend`, gets its three settings from `.env`) runs with `network_mode: service:tailscale`, so nothing is published on the host. `tailscale` is `tailscale/tailscale:v1.102.5` with hostname `party`, state in `./ts-state`.
- `ts-serve.json`: Serve on 443 → `http://127.0.0.1:8000`, `AllowFunnel` on, so the URL is `https://party.<tailnet>.ts.net`.
- Tested: the image on arm64 against the real album (sync, MediaPipe processing, login/401/429, passcode screen → wall in Chrome). Not tested here: Funnel itself, which needs your tailnet's auth key.

## 9. Pre-event runbook

1. **Tailscale + server:** set up once as in [DEPLOY.md](DEPLOY.md) (HTTPS + Funnel enabled, auth key, `.env` with `PASSCODE` and `SESSION_SECRET`). No Google Cloud project is needed with `ShareLinkSource`.
2. **Album:** create the shared album and turn on collaboration. Copy the join link into `qr_url`.
3. **Server:** put the album link in `album_url`, then `docker compose up -d --build` on the server (see [DEPLOY.md](DEPLOY.md)). `docker compose exec app python -m wall status` should show photos syncing.
4. **Test:** add a photo from a second account and confirm it shows on the wall within 2 minutes. Delete it and confirm it disappears within 5 minutes.
5. **Day before:** run `wall status`, check the album link still opens in a private browser window, and do a full dry run on a TV.
6. **At the venue:** open the URL, enter the passcode, press F. Optionally press S to pick a background.
7. **After:** stop and delete the wall as in [DEPLOY.md](DEPLOY.md) (`wall wipe`, `docker compose down`, remove the Tailscale device), then turn off sharing on the album.

## 10. Milestones

| # | Milestone | Done when |
|---|---|---|
| **M0** ✅ | **Ambient test** (go/no-go): [M0.md](M0.md). **Result: NO-GO** (partner program required), so `ShareLinkSource` it is. | A script registers a device, a *shared* album is selectable, a photo from a second account comes back from `mediaItems.list`, and the delay is measured. **If this fails, build `ShareLinkSource` instead**; everything else stays the same. |
| M1 ✅ | Backend skeleton | FastAPI, SQLite, `PhotoSource` + sync worker, downloads land in `/data`. CLI `status` (no `setup`: the share link needs no sign-in). |
| M2 ✅ | Processing + effects | Face Landmarker, effect registry, 4 effects with variants, vintage. A golden-image test set of ~20 real photos reviewed by eye. |
| M3 ✅ | Frontend wall | Mockup ported to React: themes, backgrounds, scheduler (unit tests), header and QR, polling, service worker. Notes: photos already in the album at the first poll aren't "new" (only later arrivals jump the queue and get the marker); a photo removed from the album leaves the wall at once; `/?mock` runs the wall against a fake client in dev. |
| M4 ✅ | Auth + deploy | Passcode and cookie, media auth, Docker image, compose with Tailscale Funnel. Funnel itself is verified on the first real deploy (needs the tailnet's auth key). |
| M5 | Rehearsal | Runbook steps 1–5 end to end on the real projector or a TV, with 50+ photos, running for 1 hour. |

## 11. Repository layout

```
backend/
  wall/        app.py (create_app), deps.py, schemas.py, service.py, api.py, cli.py, remote.py (typed httpx client),
               auth.py (session tokens, rate limit), store.py, sync.py, faces.py, process.py, config.py, golden.py
  wall/sources/  base.py, sharelink.py, fake.py
  wall/effects/  base.py, accessories.py (glasses, mustache, party hat), vintage.py
  assets/      glasses/*.svg, mustache/*.svg, party_hat/*.svg
  models/      face_landmarker.task
  golden/      input/ (30 public-domain photos), output/ (rendered sheets, not committed)
  tests/
frontend/      (see §6.1)
mockup/        wall-sample.html
docs/          DESIGN.md, DEPLOY.md, M0.md, M0_REPORT.md
Dockerfile, .dockerignore, docker-compose.yml, ts-serve.json, config.example.yaml, .env.example
```

## 12. Engineering conventions

**Data structures**
- Python: every structure that crosses a function boundary is a pydantic `BaseModel`. That covers source items, faces, effect results, DB rows mapped to models, API bodies and config. No loose dicts.
- TypeScript: API payload types are generated from OpenAPI. Client-only state (`WallPhoto`, `CardState`, `QueueEntry`, `Theme`, `Background`) has explicit interfaces. `strict: true`, no `any`.

**Testability**
- `create_app(deps: Deps) -> FastAPI` is an app factory. `Deps` is a pydantic model (arbitrary types allowed) holding:
  - `source: PhotoSource`
  - `store: PhotoStore`
  - `clock: Callable[[], datetime]`
  - `face_detector: FaceDetector`
  - `config: AppConfig`
- Routes get these through `Depends`, so tests pass fakes (`FakePhotoSource`, an in-memory or tmp SQLite store, a fixed clock) and call the app with `TestClient`.
- Most behaviour tests target `WallService` directly. API tests only check the wiring: auth gating, status codes, and that a route returns its service result. CLI tests use Typer's `CliRunner` and check the same wiring for commands, not the logic again.
- `FakePhotoSource` (a folder of images) is a real, shipped source (`--source fake:<dir>`). The tests and the standalone CLI use the same fake.
- Sync and processing are plain async functions with injected dependencies (`sync_once(source, store, clock)`, `process_one(photo, detector, effects, rng)`), so tests don't need timers or background tasks.
- Frontend: `scheduler.ts` is pure (state in, decision out) and takes the time and an RNG as parameters. The API client is passed into components, so tests can give them a fake.

**Tests**
- Short. One behaviour per test, with arrange/act/assert in a few lines and shared fixtures for fakes.
- Expected values are **literals**, never recomputed with the same logic as the code under test. For example, assert `order == ["new-1", "a", "b"]`, not a sort re-implemented in the test.
- Test **our** code: queue order, spawn rules, sync diffing (new/removed), effect choice being deterministic per media id, landmark-to-anchor math, auth gating, the passcode rate limit, and how the API maps from the store.
- Don't test libraries: no tests that pydantic validates a type, FastAPI routes a path, Pillow resizes, or MediaPipe finds a face. Effects get a small golden set reviewed by eye, plus a unit test of the anchor geometry, not pixel-exact snapshots.
- Tools: `pytest` + `pytest-asyncio` (backend), `vitest` (frontend).

## 13. Risks and open questions

| Risk | Mitigation |
|---|---|
| ~~Ambient unverified mode is blocked~~ **Confirmed in M0**: Ambient needs partner-program access | Use `ShareLinkSource`. Its own risks: the page format can change without notice, and it depends on the album's link staying public. Keep the parser small and tested against a saved page. |
| `mediaItems.list` is an ambient feed: the docs say it may be incomplete and repeat items, so a full re-list may not reveal deletions | Measured in M0 (`list`, `watch`; see [M0.md](M0.md)). If it isn't stable, detect deletions some other way. |
| New photos take longer than 2 min to show up in Ambient | Measured in M0. If more than about 10 min, switch to the fallback. |
| Ambient's content filter drops some photos | Accepted (decision Q18). |
| Accessories misplaced on profile faces or faces with sunglasses | Skip accessories when yaw > ~35° and fall back to vintage. Tune with the golden set. |
| Unknown projector resolution or aspect ratio | Everything is sized in vh/vw; test at 1280×720 and 1920×1080. |
| Weak venue Wi-Fi | Service worker cache plus polling that tolerates failures. Photos are small (~250 KB). |
| Funnel bandwidth limits | A few hundred ~250 KB images, cached client-side, are well under any limit. |
