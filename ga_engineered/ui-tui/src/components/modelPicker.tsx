import { useInput } from "ink";
import React, { useState } from "react";

import { DialogFrame } from "./dialog.js";
import { FuzzyPicker, type FuzzyPickerItem, clampSelection } from "./fuzzyPicker.js";

interface ModelPickerProps {
  currentModel: string;
  onSelectCurrent: () => void;
  onCancel: () => void;
}

export function ModelPicker({
  currentModel,
  onSelectCurrent,
  onCancel,
}: ModelPickerProps): React.ReactElement {
  const [selected, setSelected] = useState(0);
  const items: FuzzyPickerItem[] = [
    {
      id: "current",
      label: currentModel || "current model",
      description: "active model; backend model catalogue is not exposed yet",
    },
  ];

  useInput((_input, key) => {
    if (key.escape) onCancel();
    if (key.return) onSelectCurrent();
    if (key.upArrow) setSelected((idx) => clampSelection(idx - 1, items.length));
    if (key.downArrow) setSelected((idx) => clampSelection(idx + 1, items.length));
  });

  return (
    <DialogFrame title="model picker" instructions="Enter keep current · Esc cancel">
      <FuzzyPicker items={items} selectedIndex={selected} />
    </DialogFrame>
  );
}
