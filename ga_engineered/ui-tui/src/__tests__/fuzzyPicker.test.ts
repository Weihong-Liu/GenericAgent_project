import { describe, expect, it } from "vitest";

import { clampSelection, filterFuzzyItems, type FuzzyPickerItem } from "../components/fuzzyPicker.js";

const ITEMS: FuzzyPickerItem[] = [
  { id: "status", label: "/status", description: "Show runtime status" },
  { id: "shortcuts", label: "/shortcuts", description: "Show keyboard shortcuts" },
  { id: "model", label: "/model", hint: "<name>", description: "Change model" },
];

describe("filterFuzzyItems", () => {
  it("keeps original order for an empty query", () => {
    expect(filterFuzzyItems(ITEMS, "").map((entry) => entry.item.id)).toEqual([
      "status",
      "shortcuts",
      "model",
    ]);
  });

  it("matches across label, hint, and description", () => {
    expect(filterFuzzyItems(ITEMS, "key").map((entry) => entry.item.id)).toEqual([
      "shortcuts",
    ]);
    expect(filterFuzzyItems(ITEMS, "name").map((entry) => entry.item.id)).toEqual([
      "model",
    ]);
  });

  it("sorts tighter fuzzy matches first", () => {
    expect(filterFuzzyItems(ITEMS, "st").map((entry) => entry.item.id)[0]).toBe("status");
  });
});

describe("clampSelection", () => {
  it("keeps selected index inside the available row range", () => {
    expect(clampSelection(-2, 3)).toBe(0);
    expect(clampSelection(1, 3)).toBe(1);
    expect(clampSelection(9, 3)).toBe(2);
    expect(clampSelection(9, 0)).toBe(0);
  });
});
