import { Box, Text } from "ink";
import React from "react";

import { StructuredDiff } from "./structuredDiff.js";

interface FileEditToolDiffProps {
  diff: string;
}

export function FileEditToolDiff({ diff }: FileEditToolDiffProps): React.ReactElement {
  return (
    <Box flexDirection="column">
      <Text color="gray" dimColor>
        {"  ⎿  structured diff"}
      </Text>
      <StructuredDiff diff={diff} />
    </Box>
  );
}

export function looksLikeUnifiedDiff(text: string): boolean {
  return /^diff --git /m.test(text) || /^@@ .+ @@/m.test(text) || /^--- .+\n\+\+\+ /m.test(text);
}
