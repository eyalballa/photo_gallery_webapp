// Polling /api/photos: merge new photos, drop removed ids, survive failures.
import { HttpError, type PhotoOut, type PhotosResponse, type WallClient } from "../api/client";
import type { WallPhoto } from "../types";

export const POLL_INTERVAL_MS = 15_000;

export interface FeedState {
  photos: WallPhoto[];
  /** The last `server_time`, passed back as `since`. */
  since: string | null;
  online: boolean;
  /** True once at least one poll has succeeded. */
  loaded: boolean;
  /** The session expired or was revoked: hand back to the passcode screen. */
  unauthorized: boolean;
}

export const emptyFeed: FeedState = { photos: [], since: null, online: true, loaded: false, unauthorized: false };

export function toWallPhoto(p: PhotoOut): WallPhoto {
  return { id: p.id, url: p.url, width: p.w, height: p.h, aged: p.aged, version: p.version, firstSeen: p.first_seen };
}

/** New ids are appended, known ids replaced in place (e.g. a version bump), removed ids dropped. */
export function mergePhotos(current: readonly WallPhoto[], res: PhotosResponse): WallPhoto[] {
  const removed = new Set(res.removed);
  const incoming = new Map(res.photos.map((p) => [p.id, toWallPhoto(p)]));
  const merged = current.filter((p) => !removed.has(p.id)).map((p) => incoming.get(p.id) ?? p);
  const known = new Set(merged.map((p) => p.id));
  for (const [id, p] of incoming) if (!known.has(id) && !removed.has(id)) merged.push(p);
  return merged;
}

export async function pollOnce(client: WallClient, state: FeedState): Promise<FeedState> {
  try {
    const res = await client.photos(state.since);
    return { photos: mergePhotos(state.photos, res), since: res.server_time, online: true, loaded: true, unauthorized: false };
  } catch (e) {
    return { ...state, online: false, unauthorized: e instanceof HttpError && e.status === 401 };
  }
}
