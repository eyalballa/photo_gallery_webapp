import type { Background } from "../types";
import { blush } from "./blush";
import { champagne } from "./champagne";
import { confetti } from "./confetti";
import { film } from "./film";
import { image } from "./image";
import { partyNight } from "./partyNight";
import { sea } from "./sea";
import { space } from "./space";
import { velvet } from "./velvet";

export const BACKGROUNDS: readonly Background[] = [partyNight, confetti, space, sea, velvet, champagne, film, blush, image];

export function getBackground(id: string): Background | undefined {
  return BACKGROUNDS.find((b) => b.id === id);
}

export function backgroundsFor(themeId: string): Background[] {
  return BACKGROUNDS.filter((b) => b.themes.includes(themeId));
}
