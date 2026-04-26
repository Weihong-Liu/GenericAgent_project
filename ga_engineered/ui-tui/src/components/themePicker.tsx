import { useInput } from "ink";
import React, { useState } from "react";

import { DialogFrame } from "./dialog.js";
import { FuzzyPicker, type FuzzyPickerItem, clampSelection } from "./fuzzyPicker.js";

interface ThemePickerProps {
  currentTheme: string;
  onSelect: (theme: string) => void;
  onCancel: () => void;
}

const THEMES: FuzzyPickerItem[] = [
  { id: "default", label: "default", description: "current built-in theme" },
  { id: "custom", label: "custom themes", description: "feature-gated; no theme backend yet" },
];

export function ThemePicker({
  currentTheme,
  onSelect,
  onCancel,
}: ThemePickerProps): React.ReactElement {
  const [selected, setSelected] = useState(
    Math.max(0, THEMES.findIndex((item) => item.id === currentTheme)),
  );

  useInput((_input, key) => {
    if (key.escape) onCancel();
    if (key.return) {
      const pick = THEMES[selected] ?? THEMES[0];
      if (pick) onSelect(pick.id);
    }
    if (key.upArrow) setSelected((idx) => clampSelection(idx - 1, THEMES.length));
    if (key.downArrow) setSelected((idx) => clampSelection(idx + 1, THEMES.length));
  });

  return (
    <DialogFrame title="theme picker" instructions="Enter apply · Esc cancel">
      <FuzzyPicker items={THEMES} selectedIndex={selected} />
    </DialogFrame>
  );
}
