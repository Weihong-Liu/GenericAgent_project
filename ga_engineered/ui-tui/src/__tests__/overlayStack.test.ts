import { describe, expect, it } from "vitest";

import {
  initialOverlayStackState,
  overlayStackReducer,
  topOverlay,
} from "../state/overlayStack.js";

describe("overlayStackReducer", () => {
  it("pushes overlays and exposes the top entry", () => {
    const state = overlayStackReducer(initialOverlayStackState, {
      type: "push",
      entry: { id: "slash", kind: "picker" },
    });
    const next = overlayStackReducer(state, {
      type: "push",
      entry: { id: "help", kind: "dialog" },
    });

    expect(next.entries.map((entry) => entry.id)).toEqual(["slash", "help"]);
    expect(topOverlay(next)).toEqual({ id: "help", kind: "dialog" });
  });

  it("deduplicates pushed ids and supports replace/remove/pop/clear", () => {
    const withSlash = overlayStackReducer(initialOverlayStackState, {
      type: "push",
      entry: { id: "slash", kind: "picker" },
    });
    const deduped = overlayStackReducer(withSlash, {
      type: "push",
      entry: { id: "slash", kind: "picker" },
    });
    expect(deduped.entries).toHaveLength(1);

    const replaced = overlayStackReducer(deduped, {
      type: "replace",
      entry: { id: "history", kind: "search" },
    });
    expect(topOverlay(replaced)?.id).toBe("history");

    const removed = overlayStackReducer(replaced, { type: "remove", id: "history" });
    expect(topOverlay(removed)).toBeNull();

    const popped = overlayStackReducer(withSlash, { type: "pop" });
    expect(popped.entries).toEqual([]);

    const cleared = overlayStackReducer(withSlash, { type: "clear" });
    expect(cleared).toEqual(initialOverlayStackState);
  });
});
