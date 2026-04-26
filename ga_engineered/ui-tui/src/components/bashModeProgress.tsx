import { Box, Text } from "ink";
import React from "react";

import { SpinnerText } from "./spinner.js";

interface BashModeProgressProps {
  toolName: string;
}

export function BashModeProgress({ toolName }: BashModeProgressProps): React.ReactElement {
  return (
    <Box>
      <Text color="gray" dimColor>
        {"  ⎿  "}
      </Text>
      <SpinnerText />
      <Text color="gray" dimColor>
        {" "}
        {toolName === "shell" ? "running shell command" : "running code"}
      </Text>
    </Box>
  );
}
