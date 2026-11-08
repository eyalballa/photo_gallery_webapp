import { useEffect, useState } from "react";
import type { WallClient } from "../api/client";
import { emptyFeed, pollOnce, POLL_INTERVAL_MS, type FeedState } from "./feed";

/** Polls /api/photos every 15 s; on failure keeps the cached photos and reports offline (or unauthorized, on a 401). */
export function usePhotoFeed(client: WallClient, intervalMs = POLL_INTERVAL_MS): FeedState {
  const [feed, setFeed] = useState<FeedState>(emptyFeed);
  useEffect(() => {
    let state = emptyFeed;
    let timer = 0;
    let stopped = false;
    const run = async () => {
      state = await pollOnce(client, state);
      if (stopped) return;
      setFeed(state);
      timer = window.setTimeout(run, intervalMs);
    };
    void run();
    return () => {
      stopped = true;
      window.clearTimeout(timer);
    };
  }, [client, intervalMs]);
  return feed;
}
