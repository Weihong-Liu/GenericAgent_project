import { Box, Text } from "ink";
import React from "react";

interface SandboxPermissionRequestProps {
  mode: "approval-required" | "bypass";
}

export function SandboxPermissionRequest({
  mode,
}: SandboxPermissionRequestProps): React.ReactElement {
  return (
    <Box marginTop={1}>
      <Text color={mode === "bypass" ? "yellow" : "gray"} dimColor={mode !== "bypass"}>
        sandbox: {mode}
      </Text>
    </Box>
  );
}
