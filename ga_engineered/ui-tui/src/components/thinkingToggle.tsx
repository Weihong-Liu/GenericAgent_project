import { Box, Text, useInput } from "ink";
import React from "react";

import { DialogFrame } from "./dialog.js";

interface ThinkingToggleProps {
  enabled: boolean;
  onToggle: () => void;
  onCancel: () => void;
}

export function ThinkingToggle({
  enabled,
  onToggle,
  onCancel,
}: ThinkingToggleProps): React.ReactElement {
  useInput((_input, key) => {
    if (key.escape) onCancel();
    if (key.return || key.tab) onToggle();
  });

  return (
    <DialogFrame title="thinking mode" instructions="Enter toggle · Esc cancel">
      <Box>
        <Text color={enabled ? "cyan" : "gray"} bold>
          {enabled ? "on" : "off"}
        </Text>
        <Text color="gray" dimColor>
          {"  "}UI marker only; backend effort control is tracked for a later command task.
        </Text>
      </Box>
    </DialogFrame>
  );
}
