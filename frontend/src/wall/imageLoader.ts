// Pre-decodes the next photo (img.decode()) so a card never enters half-loaded.
const RETRY_AFTER_MS = 60_000;

export class ImageLoader {
  private readonly ready = new Map<string, HTMLImageElement>();
  private readonly pending = new Set<string>();
  private readonly failedAt = new Map<string, number>();

  load(url: string): void {
    if (this.ready.has(url) || this.pending.has(url)) return;
    this.pending.add(url);
    const img = new Image();
    img.decoding = "async";
    img.alt = "";
    img.src = url;
    img
      .decode()
      .then(() => {
        this.ready.set(url, img);
        this.failedAt.delete(url);
      })
      .catch(() => this.failedAt.set(url, performance.now()))
      .finally(() => this.pending.delete(url));
  }

  isReady(url: string): boolean {
    return this.ready.has(url);
  }

  /** Failed recently (offline and not cached, or a bad file): skip it for a while. */
  isFailing(url: string, now: number): boolean {
    const at = this.failedAt.get(url);
    return at !== undefined && now - at < RETRY_AFTER_MS;
  }

  /** Drops decoded images other than `keep`, so photos picked and then skipped don't pile up in memory. */
  retain(keep: ReadonlySet<string>): void {
    for (const url of this.ready.keys()) if (!keep.has(url)) this.ready.delete(url);
  }

  /** Hands the decoded element to a card; the loader forgets it. */
  take(url: string): HTMLImageElement | undefined {
    const img = this.ready.get(url);
    this.ready.delete(url);
    return img;
  }
}
