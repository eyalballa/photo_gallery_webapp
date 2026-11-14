import { describe, expect, it } from "vitest";
import { HttpError, type PhotoOut, type PhotosResponse, type WallClient } from "../api/client";
import { emptyFeed, mergePhotos, pollOnce, toWallPhoto } from "./feed";

const out = (id: string, version = 1): PhotoOut => ({
  id, w: 1600, h: 1200, aged: false, first_seen: "2026-11-06T12:00:00Z", version, url: `/media/${id}.jpg?v=${version}`,
});
const res = (photos: PhotoOut[], removed: string[] = [], server_time = "2026-11-06T12:01:00Z"): PhotosResponse => ({
  photos, removed, server_time,
});
const fakeClient = (reply: PhotosResponse | Error, calls: (string | null)[] = []): WallClient => ({
  login: async () => "ok",
  publicConfig: async () => ({ login_title: "Photo wall" }),
  config: async () => ({ kind: "unauthorized" }),
  photos: async (since) => {
    calls.push(since);
    if (reply instanceof Error) throw reply;
    return reply;
  },
  effects: async () => ({ effects: [], honoree: null }),
  setEffects: async () => ({ effects: [], honoree: null }),
  rerollEffects: async () => ({ queued: 0 }),
});

describe("mergePhotos", () => {
  it("appends new photos, drops removed ids and replaces re-processed ones", () => {
    const current = [toWallPhoto(out("a")), toWallPhoto(out("b")), toWallPhoto(out("c"))];
    const merged = mergePhotos(current, res([out("b", 2), out("d")], ["a"]));
    expect(merged.map((p) => `${p.id}@${p.version}`)).toEqual(["b@2", "c@1", "d@1"]);
  });

  it("ignores a photo listed as both new and removed", () => {
    expect(mergePhotos([], res([out("x")], ["x"]))).toEqual([]);
  });
});

describe("pollOnce", () => {
  it("passes the previous server_time back as since", async () => {
    const calls: (string | null)[] = [];
    const client = fakeClient(res([out("a")], [], "2026-11-06T12:05:00Z"), calls);
    const first = await pollOnce(client, emptyFeed);
    await pollOnce(client, first);
    expect(calls).toEqual([null, "2026-11-06T12:05:00Z"]);
  });

  it("keeps cached photos and goes offline when the request fails", async () => {
    const cached = { photos: [toWallPhoto(out("a"))], since: "t1", online: true, loaded: true, unauthorized: false };
    const next = await pollOnce(fakeClient(new Error("network")), cached);
    expect([next.photos.map((p) => p.id), next.since, next.online, next.unauthorized]).toEqual([["a"], "t1", false, false]);
  });

  it("reports unauthorized on a 401, so the wall hands back to the passcode screen", async () => {
    const next = await pollOnce(fakeClient(new HttpError(401, "/api/photos")), emptyFeed);
    expect(next.unauthorized).toBe(true);
  });
});
