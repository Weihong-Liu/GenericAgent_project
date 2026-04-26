/**
 * ASCII art and gradient palette for the welcome banner.
 *
 * The visual language follows hermes-agent's startup banner pattern: a wide
 * block-letter brand mark paired with a compact emblem panel on the left when
 * the terminal is wide enough.
 */

export interface Palette {
  bright: string;
  accent: string;
  deep: string;
  dim: string;
}

export const DEFAULT_PALETTE: Palette = {
  bright: "#7EB8F6",
  accent: "#8EA8FF",
  deep: "#4169E1",
  dim: "#4B5563",
};

/** A single rendered line: ``[hexColor, text]``. */
export type Line = readonly [string, string];

// "GENERIC AGENT" rendered in the ANSI Shadow block font.
//
// Width is 102 cols. The compact form (below) drops to 25 cols for
// terminals narrower than the wide threshold.
export const LOGO_ART: readonly string[] = [
  " ██████╗ ███████╗███╗   ██╗███████╗██████╗ ██╗ ██████╗      █████╗  ██████╗ ███████╗███╗   ██╗████████╗",
  "██╔════╝ ██╔════╝████╗  ██║██╔════╝██╔══██╗██║██╔════╝     ██╔══██╗██╔════╝ ██╔════╝████╗  ██║╚══██╔══╝",
  "██║  ███╗█████╗  ██╔██╗ ██║█████╗  ██████╔╝██║██║          ███████║██║  ███╗█████╗  ██╔██╗ ██║   ██║   ",
  "██║   ██║██╔══╝  ██║╚██╗██║██╔══╝  ██╔══██╗██║██║          ██╔══██║██║   ██║██╔══╝  ██║╚██╗██║   ██║   ",
  "╚██████╔╝███████╗██║ ╚████║███████╗██║  ██║██║╚██████╗     ██║  ██║╚██████╔╝███████╗██║ ╚████║   ██║   ",
  " ╚═════╝ ╚══════╝╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝╚═╝ ╚═════╝     ╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝   ╚═╝   ",
];

// GenericAgent-specific emblem: core runtime, tools, memory, and local-first
// execution as a compact system diagram.
export const EMBLEM_ART: readonly string[] = [
  "      +----------------+      ",
  "      | GENERIC AGENT  |      ",
  "  +---+----------------+---+  ",
  "  |   | CORE RUNTIME   |   |  ",
  "  |   | TOOL GRAPH     |   |  ",
  "  |   | MEMORY LAYERS  |   |  ",
  "  +---+----------------+---+  ",
  "      | PLAN -> ACT    |      ",
  "      | CHECK -> LEARN |      ",
  "  +---+----------------+---+  ",
  "  |   |  GA ENGINE     |   |  ",
  "  +---+----------------+---+  ",
  "      |  LOCAL FIRST   |      ",
  "      +----------------+      ",
];

// Compact mark for narrow terminals. ~25 cols wide.
export const COMPACT_LOGO: readonly string[] = [
  "  ██████╗     █████╗ ",
  " ██╔════╝    ██╔══██╗",
  " ██║  ███╗   ███████║",
  " ██║   ██║   ██╔══██║",
  " ╚██████╔╝██╗██║  ██║",
  "  ╚═════╝ ╚═╝╚═╝  ╚═╝",
];

export const LOGO_WIDTH = LOGO_ART[0]?.length ?? 0;
export const EMBLEM_WIDTH = EMBLEM_ART[0]?.length ?? 0;
export const COMPACT_LOGO_WIDTH = COMPACT_LOGO[0]?.length ?? 0;

/** Margin between the emblem column and the logo column, in cols. */
export const EMBLEM_LOGO_GAP = 2;

/**
 * Minimum terminal width to render the wide LOGO_ART without horizontal
 * overflow. Set to ``LOGO_WIDTH + 1`` so even single-column padding from
 * Ink's flex layout is safe.
 */
export const WIDE_LOGO_THRESHOLD = LOGO_WIDTH + 1;

/**
 * Minimum terminal width to render the side-by-side "emblem + logo +
 * session panel" layout. Anything narrower stacks the logo above the
 * session panel and drops the emblem entirely.
 */
export const SPLIT_LAYOUT_THRESHOLD =
  LOGO_WIDTH + EMBLEM_LOGO_GAP + EMBLEM_WIDTH + 1;

/** A six-row gradient mapped onto the LOGO_ART rows: bright → accent → deep. */
const LOGO_GRADIENT = [0, 0, 1, 1, 2, 2] as const;

/**
 * 14-row gradient for the emblem panel — bright title, blue body, dim footer.
 */
const EMBLEM_GRADIENT = [2, 2, 1, 1, 0, 0, 1, 1, 2, 2, 3, 3, 3, 3] as const;

const COMPACT_GRADIENT = [0, 0, 1, 1, 2, 2] as const;

function colorize(
  art: readonly string[],
  gradient: readonly number[],
  palette: Palette,
): Line[] {
  const wheel = [palette.bright, palette.accent, palette.deep, palette.dim];
  return art.map((text, i): Line => {
    const idx = gradient[i] ?? 3;
    const color = wheel[idx] ?? palette.dim;
    return [color, text];
  });
}

export function logo(palette: Palette = DEFAULT_PALETTE): Line[] {
  return colorize(LOGO_ART, LOGO_GRADIENT, palette);
}

export function compactLogo(palette: Palette = DEFAULT_PALETTE): Line[] {
  return colorize(COMPACT_LOGO, COMPACT_GRADIENT, palette);
}

export function emblem(palette: Palette = DEFAULT_PALETTE): Line[] {
  return colorize(EMBLEM_ART, EMBLEM_GRADIENT, palette);
}

/** Pick the appropriate logo art for a given terminal width. */
export function selectLogo(width: number, palette: Palette = DEFAULT_PALETTE): Line[] {
  return width >= WIDE_LOGO_THRESHOLD ? logo(palette) : compactLogo(palette);
}
