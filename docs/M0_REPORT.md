# M0 Report: Photo Source Go/No-Go

2026-11-06

## Summary

The Google Photos Ambient API is a **NO-GO**, and the album's public share link is a **GO**. Ambient
rejects device registration for apps outside Google's Photos partner program. The share link needs
no login. Photos from other contributors appear about 6 s after upload, deletions disappear on the
next fetch, and a 114-item album comes back in a single request.

The photo wall will read the shared album through `ShareLinkSource`. Nothing downstream in the design
changes, so M1 (backend skeleton) can start.

## Background

M0 was the go/no-go gate for the photo source. DESIGN.md §10 required a live result: a device
registered, a shared album selected, a photo from a second account returned by the API, and the delay
measured. If that failed, the fallback was the album's public share link.

> The probe code (`wall/m0.py`, `wall/sources/ambient.py`, their tests and `GOOGLE_SETUP.md`) was removed on 2026-11-08, after the Google Cloud project was deleted. This report is the record of what was measured.

What was built for the test:

- `backend/wall/sources/ambient.py`: a typed Ambient API client. It covers the OAuth device flow,
  token storage (file mode 600), device create/get/delete, paged listing with de-duplication, and
  download.
- `backend/wall/m0.py`: the probe CLI, with `auth`, `device`, `list`, `watch`, `download` and
  `reset` commands.
- 9 unit tests covering sign-in polling, token refresh, paging, error mapping and change detection.
- `docs/M0.md` (runbook and raw results) and `docs/GOOGLE_SETUP.md` (step-by-step Cloud Console setup).

## Ambient API test

Sign-in worked, but device registration was refused, so none of the later checks could run.

Setup: a new Cloud project with the Photos Ambient API enabled, an External consent screen in
Testing mode with account A as a test user, and a "TVs and Limited Input devices" OAuth client.

| Check | Result |
|---|---|
| Unverified app gets a token for `photosambient.mediaitems` | ✅ Pass, after adding account A as a test user (the first try returned `403 access_denied`) |
| Device is created and its settings link opens | ❌ **Fail**: `PERMISSION_DENIED` |
| Shared album can be picked as a source | ⛔ Not reachable (no device) |
| Second-account photo is returned | ⛔ Not reachable |
| Delay from upload to visible | ⛔ Not reachable |
| Deletion is visible | ⛔ Not reachable |
| 1600 px download is a JPEG | ⛔ Not reachable |

The exact error from `devices.create`:

> PERMISSION_DENIED: You do not have permission to perform the requested operation. Please refer to
> the partner program at https://developers.google.com/photos/partner-program/overview.

The design assumed Ambient would work in unverified or test mode. It doesn't: the device endpoints
require Google Photos partner-program membership, which a one-off personal project can't count on
getting.

## Share-link spike

The share link passed every check. The test used album `shared_test`, owned by account A, with
photos added from account B. A script polled the album every 20 s.

### How a fetch works

1. Request the short link (`photos.app.goo.gl/…`) with a **non-browser** User-Agent. It returns
   HTTP 302 to `https://photos.google.com/share/<albumId>?key=<key>`. A browser User-Agent gets a
   JavaScript landing page with no redirect.
2. Request that URL with a **browser** User-Agent. The page embeds the album as JSON in an
   `AF_initDataCallback({key: 'ds:1', … data: […]})` block. No login or cookies are needed.
3. Download each photo as `<base URL>=w1600-h1600`, which returns a JPEG of about 240 KB with no
   auth. `=d` returns the original file.

### Data layout (`ds:1`)

| Field | Location |
|---|---|
| Stable media id (`AF1Qip…`) | `data[1][i][0]` |
| Image base URL (`lh3.googleusercontent.com/pw/…`) | `data[1][i][1][0]` |
| Width, height | `data[1][i][1][1]`, `data[1][i][1][2]` |
| File size in bytes (missing on some items) | `data[1][i][1][9][0]` |
| Taken time (ms since epoch) | `data[1][i][2]` |
| Timezone offset (ms) | `data[1][i][4]` |
| Time added to the album (ms since epoch) | `data[1][i][5]` |
| Contributor id | `data[1][i][6][0]` |
| Video marker: `[duration_ms, null, w, h, …, [video_url]]` | key `"76647426"` in the item's last element (a dict) |
| Next-page token (`''` = no more pages) | `data[2]` |
| Album title | `data[3][1]` |
| Total item count | `data[3][21]` |

### Results

| Check | Result |
|---|---|
| Photos from another contributor appear | ✅ All 7 photos from account B, each with B's contributor id |
| Delay from upload to visible | ✅ **About 6 s** after Google's "added" time, on the next poll |
| Deletions disappear | ✅ On the next poll (within 20 s) |
| 1600 px download | ✅ `image/jpeg`, 239 KB (original 1.3 MB) |
| Large album | ✅ 114 items (113 photos + 1 video) in one page; `data[2]` empty; total count matched |
| Video detection | ✅ Only the video carried the `"76647426"` key |

## Decision and design changes

**`ShareLinkSource` is the photo source.** The Ambient client was kept as a standby at first, then
removed with the Google Cloud project.

Changes made to `docs/DESIGN.md`:

- **Photo source:** now the album's share link. `AmbientSource` is the fallback.
- **Sync cadence:** one fetch every 90 s. Each fetch returns the whole album, so new photos and
  deletions come from the same call. This replaces the separate "new photos every 90 s, full re-list
  every 5 min" schedule, and the Ambient call quota no longer applies.
- **Risks:** the Ambient risk is marked confirmed, and the share link's own risks are added.
- **Milestones:** M0 is marked done, with a NO-GO for Ambient.

The share link also beats what Ambient would have offered: about 6 s to visibility instead of
minutes, and reliable deletion detection because every fetch is a complete listing.

## Risks and open questions

| Risk | Mitigation |
|---|---|
| Google changes the page format; this is undocumented | Keep the parser small and test it against a saved copy of the page. If `ds:1` fails to parse, log loudly and keep showing cached photos. |
| Albums past some size load in pages (the limit isn't known; past reports put it around 300–500) | On every fetch, compare `len(data[1])` with `data[3][21]`. On a mismatch, warn and don't mark missing items as removed. Add `batchexecute` paging only if this ever fires. |
| Live / motion photos may carry the video marker and get skipped | Include one in the M2 golden set and check. |
| The album link stops working (sharing turned off or link reset) | `wall status` reports the last successful fetch. The runbook adds a check that the link is still public. |
| Google rate-limits a fetch every 90 s | Not seen in the spike (about 20 fetches in 7 min). Back off on 429 or 5xx responses. |

## Next steps

1. **M1, backend skeleton:** `ShareLinkSource` and `FakePhotoSource` behind `PhotoSource`, the
   SQLite store, a 90 s sync worker that downloads new photos to `/data/originals`, `WallService`,
   the Typer CLI (`sync`, `photos`, `status`, `serve`), and the FastAPI app factory, with tests per
   DESIGN.md §12.
2. Save the spike's album page as a test fixture for the parser.
3. **Optional cleanup:** revoke the Ambient probe's access at https://myaccount.google.com/permissions
   and delete `backend/data/token.json`.
