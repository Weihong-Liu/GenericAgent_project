import { Box, Text } from "ink";
import React from "react";

import { SpinnerText } from "./spinner.js";

interface ToolUseLoaderProps {
  toolName: string;
}

export function ToolUseLoader({ toolName }: ToolUseLoaderProps): React.ReactElement {
  return (
    <Box>
      <Text color="gray" dimColor>
        {"  ⎿  "}
      </Text>
      <SpinnerText />
      <Text color="gray" dimColor>
        {" "}
        waiting for {toolName}
      </Text>
    </Box>
  );
}
