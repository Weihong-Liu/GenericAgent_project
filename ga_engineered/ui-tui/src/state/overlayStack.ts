export interface OverlayEntry {
  id: string;
  kind: string;
}

export interface OverlayStackState {
  entries: readonly OverlayEntry[];
}

export type OverlayStackAction =
  | { type: "push"; entry: OverlayEntry }
  | { type: "replace"; entry: OverlayEntry }
  | { type: "pop" }
  | { type: "remove"; id: string }
  | { type: "clear" };

export const initialOverlayStackState: OverlayStackState = { entries: [] };

export function overlayStackReducer(
  state: OverlayStackState,
  action: OverlayStackAction,
): OverlayStackState {
  switch (action.type) {
    case "push":
      return {
        entries: [...state.entries.filter((entry) => entry.id !== action.entry.id), action.entry],
      };
    case "replace":
      return { entries: [action.entry] };
    case "pop":
      return { entries: state.entries.slice(0, -1) };
    case "remove":
      return { entries: state.entries.filter((entry) => entry.id !== action.id) };
    case "clear":
      return initialOverlayStackState;
  }
}

export function topOverlay(state: OverlayStackState): OverlayEntry | null {
  return state.entries[state.entries.length - 1] ?? null;
}
