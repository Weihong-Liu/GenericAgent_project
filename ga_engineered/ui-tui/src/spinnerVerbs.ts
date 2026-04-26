/**
 * Verb pool for the thinking spinner. A turn picks one at random on
 * start and sticks with it until the turn ends. Curated subset of the
 * vibe free-code uses (Pondering, Waddling, Cogitating, …).
 */

export const SPINNER_VERBS: readonly string[] = [
  "Accomplishing",
  "Actioning",
  "Analyzing",
  "Brewing",
  "Calibrating",
  "Cogitating",
  "Composing",
  "Computing",
  "Concentrating",
  "Conjuring",
  "Considering",
  "Crafting",
  "Crunching",
  "Decoding",
  "Deliberating",
  "Determining",
  "Distilling",
  "Excogitating",
  "Forging",
  "Formulating",
  "Inferring",
  "Inspecting",
  "Investigating",
  "Mapping",
  "Marinating",
  "Mulling",
  "Musing",
  "Noodling",
  "Orchestrating",
  "Percolating",
  "Plotting",
  "Pondering",
  "Pontificating",
  "Processing",
  "Puzzling",
  "Reasoning",
  "Reflecting",
  "Reticulating",
  "Ruminating",
  "Scrutinizing",
  "Simmering",
  "Spelunking",
  "Strategizing",
  "Synthesizing",
  "Thinking",
  "Tinkering",
  "Untangling",
  "Waddling",
  "Whirring",
  "Wrangling",
] as const;

export function pickVerb(seed: number = Math.random()): string {
  const idx = Math.floor(seed * SPINNER_VERBS.length);
  return SPINNER_VERBS[idx] ?? "Pondering";
}
