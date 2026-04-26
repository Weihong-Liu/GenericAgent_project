/**
 * Theme palette mirroring free-code's dark theme.
 *
 * RGB values are copied verbatim from
 * ``free-code/src/utils/theme.ts`` so the visual identity matches
 * pixel-for-pixel. Ink accepts ``rgb(R,G,B)`` strings as colour values
 * directly, no conversion needed.
 */

export interface Theme {
  /** Brand orange — primary accent (assistant verbs, key callouts). */
  claude: string;
  /** Welcome / banner accent — pastel green. */
  startupAccent: string;
  /** Bash mode indicator. */
  bashBorder: string;
  /** Default text colour for transcript content. */
  text: string;
  /** Mid-grey for borders / hints. */
  subtle: string;
  /** Darker grey for inactive UI / loading state. */
  inactive: string;
  /** Cool blue for completion suggestions / link text. */
  suggestion: string;
  /** Status / outcome colours. */
  success: string;
  warning: string;
  error: string;
}

export const DARK_THEME: Theme = {
  claude: "rgb(215,119,87)",
  startupAccent: "rgb(124,176,133)",
  bashBorder: "rgb(255,200,87)",
  text: "rgb(229,229,229)",
  subtle: "rgb(175,175,175)",
  inactive: "rgb(102,102,102)",
  suggestion: "rgb(87,105,247)",
  success: "rgb(44,122,57)",
  warning: "rgb(150,108,30)",
  error: "rgb(171,43,63)",
};

export const THEME = DARK_THEME;
