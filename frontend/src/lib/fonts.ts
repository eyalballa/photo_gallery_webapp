const loaded = new Set<string>();

/** Adds one Google Fonts stylesheet per family list, once. */
export function ensureFonts(families: readonly string[]): void {
  const key = families.join("|");
  if (loaded.has(key) || families.length === 0) return;
  loaded.add(key);
  const query = families.map((f) => `family=${f.replace(/ /g, "+")}`).join("&");
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = `https://fonts.googleapis.com/css2?${query}&display=swap`;
  document.head.appendChild(link);
}
