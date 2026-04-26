import { Box, Text } from "ink";
import { homedir } from "node:os";
import React from "react";

import {
  DEFAULT_PALETTE,
  EMBLEM_LOGO_GAP,
  SPLIT_LAYOUT_THRESHOLD,
  emblem,
  selectLogo,
  type Line,
} from "../banner.js";
import type { RuntimeStatus } from "../schemas.js";
import { THEME } from "../theme.js";

export const RECENT_RELEASE_NOTES = [
  "Use /rate-limit-options when provider or token budget pressure appears.",
] as const;

interface WelcomeProps {
  width: number;
  status: RuntimeStatus | null;
}

function ArtLines({ lines }: { lines: readonly Line[] }): React.ReactElement {
  return (
    <Box flexDirection="column">
      {lines.map(([color, text], index) => (
        <Text key={`${index}-${text}`} color={color} bold>
          {text}
        </Text>
      ))}
    </Box>
  );
}

export function Welcome({ width, status }: WelcomeProps): React.ReactElement {
  const cwd = process.cwd().replace(homedir(), "~");
  const runtime = status
    ? `${status.provider} · ${status.model} · ${status.session_id}`
    : "loading runtime...";
  const releaseLine = RECENT_RELEASE_NOTES[0] ?? "";
  const contentWidth = Math.max(1, width - 4);
  const showEmblem = contentWidth >= SPLIT_LAYOUT_THRESHOLD;
  const logoLines = selectLogo(
    showEmblem ? contentWidth - EMBLEM_LOGO_GAP : contentWidth,
    DEFAULT_PALETTE,
  );
  const emblemLines = showEmblem ? emblem(DEFAULT_PALETTE) : [];
  return (
    <Box
      flexDirection="column"
      borderStyle="round"
      borderColor={DEFAULT_PALETTE.deep}
      paddingX={1}
      marginBottom={1}
    >
      <Box flexDirection="row">
        {showEmblem ? (
          <Box marginRight={EMBLEM_LOGO_GAP}>
            <ArtLines lines={emblemLines} />
          </Box>
        ) : null}
        <Box flexDirection="column">
          <ArtLines lines={logoLines} />
          <Text>
            <Text color={DEFAULT_PALETTE.bright} bold>
              ✻ GenericAgent
            </Text>
            <Text color={THEME.subtle} dimColor>
              {" "}
              v{status?.gateway_version ?? "loading"}
            </Text>
          </Text>
        </Box>
      </Box>
      <Text color={THEME.subtle} dimColor>
        {"  "}
        {runtime}
        {" · "}
        {cwd}
      </Text>
      {releaseLine ? (
        <Text color={DEFAULT_PALETTE.accent}>
          {"  "}
          {releaseLine}
        </Text>
      ) : null}
      <Text color={THEME.subtle} dimColor>
        {"  "}/help commands · ! shell · @ files · ? shortcuts
      </Text>
    </Box>
  );
}
