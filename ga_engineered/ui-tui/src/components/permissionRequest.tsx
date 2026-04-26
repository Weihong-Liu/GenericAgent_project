import { Box, Text, useInput } from "ink";
import React from "react";

import type { ApprovalDecision } from "../schemas.js";

export interface PermissionRequestProps {
  toolName: string;
  argumentsPreview: string;
  onDecide: (decision: ApprovalDecision) => void;
}

export function PermissionRequest({
  toolName,
  argumentsPreview,
  onDecide,
}: PermissionRequestProps): React.ReactElement {
  useInput((input, key) => {
    if (key.escape || input === "n" || input === "N") {
      onDecide("deny");
      return;
    }
    if (input === "y" || input === "Y" || key.return) {
      onDecide("allow_once");
      return;
    }
    if (input === "a" || input === "A") {
      onDecide("allow_always");
    }
  });

  return (
    <Box flexDirection="column" marginTop={1} borderStyle="round" borderColor="yellow" paddingX={1}>
      <Text color="yellow">tool permission requested: {toolName}</Text>
      {argumentsPreview ? (
        <Text color="gray" dimColor>
          {argumentsPreview}
        </Text>
      ) : null}
      <Text>
        <Text color="green">y allow once</Text>
        <Text color="gray"> · </Text>
        <Text color="cyan">a always allow tool</Text>
        <Text color="gray"> · </Text>
        <Text color="red">n deny</Text>
        <Text color="gray"> · Esc deny</Text>
      </Text>
    </Box>
  );
}
