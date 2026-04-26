import { Box, Text } from "ink";
import React from "react";

export interface DialogFrameProps {
  title: string;
  accentColor?: string;
  instructions?: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
  border?: boolean;
}

/**
 * Shared frame for transient TUI overlays. Keep this intentionally small:
 * free-code has many dialog variants, but ga_engineered needs one stable
 * shell before layering command-specific behavior on top.
 */
export function DialogFrame({
  title,
  accentColor = "cyan",
  instructions,
  children,
  footer,
  border = false,
}: DialogFrameProps): React.ReactElement {
  return (
    <Box
      flexDirection="column"
      marginTop={1}
      borderStyle={border ? "round" : undefined}
      borderColor={border ? accentColor : undefined}
      paddingX={border ? 1 : 0}
    >
      <Text color={accentColor}>
        ── {title} ──{" "}
        {instructions ? (
          <Text color="gray" dimColor>
            {instructions}
          </Text>
        ) : null}
      </Text>
      {children}
      {footer ? (
        <Text color="gray" dimColor>
          {footer}
        </Text>
      ) : null}
    </Box>
  );
}
