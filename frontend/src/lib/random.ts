export const rand = (a: number, b: number): number => a + Math.random() * (b - a);

export function pick<T>(items: readonly T[]): T {
  const item = items[Math.floor(Math.random() * items.length)];
  if (item === undefined) throw new Error("pick() from an empty list");
  return item;
}

/** "#ff5d73" → "255,93,115", for rgba() strings. */
export function hexToRgb(hex: string): string {
  return [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16)).join(",");
}
