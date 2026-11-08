/// <reference lib="webworker" />
// Cache-first for processed photos, so the wall keeps cycling through Wi-Fi drops.
// Each URL carries ?v=<version>, so a re-processed photo is a new cache entry.
const sw = self as unknown as ServiceWorkerGlobalScope;
const CACHE = "wall-media-v1"; // PasscodeGate deletes it when there's no valid session

sw.addEventListener("install", () => {
  void sw.skipWaiting();
});

sw.addEventListener("activate", (event) => {
  event.waitUntil(sw.clients.claim());
});

sw.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== "GET" || url.origin !== sw.location.origin || !url.pathname.startsWith("/media/")) return;
  event.respondWith(cacheFirst(event, event.request));
});

async function cacheFirst(event: FetchEvent, request: Request): Promise<Response> {
  const cache = await caches.open(CACHE);
  const hit = await cache.match(request);
  if (hit) return hit;
  const res = await fetch(request);
  // a failed cache write (quota) must not turn a good response into a broken image
  if (res.ok) event.waitUntil(store(cache, request, res.clone()).catch(() => {}));
  return res;
}

/** Caches the response and drops other versions (?v=) of the same photo, so the cache doesn't only grow. */
async function store(cache: Cache, request: Request, res: Response): Promise<void> {
  await cache.put(request, res);
  const path = new URL(request.url).pathname;
  for (const old of await cache.keys()) {
    if (old.url !== request.url && new URL(old.url).pathname === path) await cache.delete(old);
  }
}

export {};
