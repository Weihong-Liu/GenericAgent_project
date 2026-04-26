import { Box, Text } from "ink";
import React from "react";

import { Markdown } from "../markdown/renderer.js";
import type { TranscriptItem } from "../state/transcriptStore.js";
import { THEME } from "../theme.js";
import {
  extractToolArgument,
  formatCollapsedPreview,
  summariseToolResult,
} from "../toolSummary.js";
import { BashModeProgress } from "./bashModeProgress.js";
import { FileEditToolDiff, looksLikeUnifiedDiff } from "./fileEditToolDiff.js";
import { SpinnerText, StreamCursor } from "./spinner.js";
import { formatDuration, ThinkingIndicator } from "./thinkingIndicator.js";
import { ToolUseLoader } from "./toolUseLoader.js";

interface MessageRowProps {
  item: TranscriptItem;
  selected?: boolean;
  transcriptMode?: boolean;
}

export function MessageRow({
  item,
  selected = false,
  transcriptMode = false,
}: MessageRowProps): React.ReactElement {
  const marker = selected ? <Text color="cyan">┃ </Text> : null;
  return (
    <Box>
      {marker}
      <Box flexDirection="column" flexGrow={1}>
        <TranscriptRow item={item} transcriptMode={transcriptMode} />
      </Box>
    </Box>
  );
}

function TranscriptRow({
  item,
  transcriptMode,
}: {
  item: TranscriptItem;
  transcriptMode: boolean;
}): React.ReactElement {
  switch (item.kind) {
    case "user":
      return (
        <Box>
          <Text color={THEME.suggestion}>{"❯ "}</Text>
          <Text color={THEME.text}>{item.text}</Text>
        </Box>
      );
    case "assistant": {
      const thoughtForMs =
        item.first_token_at != null ? item.first_token_at - item.started_at : 0;
      if (item.streaming) {
        return (
          <Box flexDirection="column">
            <ThinkingIndicator
              startedAt={item.started_at}
              targetTokens={Math.floor(item.text.length / 4)}
              thoughtForMs={thoughtForMs}
            />
            <Box>
              <Text color={THEME.claude}>{"⏺ "}</Text>
              <Box flexDirection="column" flexGrow={1}>
                <Markdown source={item.text} suffix={<StreamCursor />} />
              </Box>
            </Box>
          </Box>
        );
      }
      return (
        <Box flexDirection="column">
          <Box>
            <Text color={THEME.claude}>{"⏺ "}</Text>
            <Box flexDirection="column" flexGrow={1}>
              <Markdown source={item.text} />
            </Box>
          </Box>
          {item.finished_at != null ? (
            <Text color={THEME.subtle} dimColor>
              {"✻ Crunched for "}
              {formatDuration(item.finished_at - item.started_at)}
            </Text>
          ) : null}
        </Box>
      );
    }
    case "tool":
      return <ToolRow item={item} transcriptMode={transcriptMode} />;
    case "system":
      return (
        <Text color={THEME.subtle} dimColor>
          {item.text}
        </Text>
      );
    case "error":
      return <Text color={THEME.error}>✗ {item.text}</Text>;
  }
}

function ToolRow({
  item,
  transcriptMode,
}: {
  item: Extract<TranscriptItem, { kind: "tool" }>;
  transcriptMode: boolean;
}): React.ReactElement {
  const isRunning = item.status === "running";
  const isError = item.status === "error";
  const headColor =
    isRunning ? THEME.warning : isError ? THEME.error : THEME.claude;
  const elapsed =
    item.finished_at != null
      ? `${((item.finished_at - item.started_at) / 1000).toFixed(1)}s`
      : "";
  const toolTitle = displayToolName(item.name);
  const argSummary = displayToolArgs(item.name, item.args_preview);
  const resultText = item.result_full || item.result_preview;
  const effectiveExpanded = transcriptMode || item.expanded;
  const shellPreview =
    item.collapsed && !effectiveExpanded && isShellLikeTool(item.name) && resultText
      ? formatCollapsedPreview(resultText)
      : null;
  const summaryLine =
    item.collapsed && !effectiveExpanded && !shellPreview
      ? summariseToolResult(item.name, resultText, isError)
      : null;
  const showFullBody = !summaryLine && !shellPreview && (effectiveExpanded || !item.collapsed);

  return (
    <Box flexDirection="column">
      <Box>
        <Text color={headColor}>⏺ </Text>
        {isRunning ? <SpinnerText /> : null}
        {isRunning ? <Text> </Text> : null}
        <Text color={THEME.text}>{toolTitle}</Text>
        {argSummary ? (
          <Text color={THEME.subtle} dimColor>
            ({argSummary})
          </Text>
        ) : null}
        {elapsed ? (
          <Text color={THEME.inactive} dimColor>
            {" "}
            {elapsed}
          </Text>
        ) : null}
      </Box>
      {isRunning ? (
        isShellLikeTool(item.name) ? (
          <BashModeProgress toolName={item.name} />
        ) : (
          <ToolUseLoader toolName={item.name} />
        )
      ) : null}
      {shellPreview ? (
        <CollapsedResultPreview
          lines={shellPreview.lines}
          hiddenLines={shellPreview.hiddenLines}
          isError={isError}
        />
      ) : null}
      {summaryLine ? (
        <Box>
          <Text color={isError ? THEME.error : THEME.subtle} dimColor={!isError}>
            {"  ⎿  "}
            {summaryLine}
            {" "}(ctrl+o to expand)
          </Text>
        </Box>
      ) : null}
      {showFullBody && resultText ? (
        item.name === "file_patch" || looksLikeUnifiedDiff(resultText) ? (
          <FileEditToolDiff diff={resultText} />
        ) : (
          <ResultBody text={resultText} isError={isError} />
        )
      ) : null}
    </Box>
  );
}

function CollapsedResultPreview({
  lines,
  hiddenLines,
  isError,
}: {
  lines: string[];
  hiddenLines: number;
  isError: boolean;
}): React.ReactElement {
  return (
    <Box flexDirection="column">
      {lines.map((line, idx) => (
        <Box key={idx}>
          <Text color={THEME.subtle} dimColor>
            {idx === 0 ? "  ⎿  " : "     "}
          </Text>
          <Text color={isError ? THEME.error : THEME.subtle} dimColor={!isError}>
            {line}
          </Text>
        </Box>
      ))}
      {hiddenLines > 0 ? (
        <Box>
          <Text color={THEME.subtle} dimColor>
            {"     … +"}
            {hiddenLines}
            {" lines (ctrl+o to expand)"}
          </Text>
        </Box>
      ) : null}
    </Box>
  );
}

function displayToolName(name: string): string {
  switch (name) {
    case "shell":
      return "Bash";
    case "code_run":
      return "Python";
    default:
      return name;
  }
}

function displayToolArgs(name: string, argsPreview: string): string {
  if (!argsPreview) return "";
  if (name === "shell") {
    return truncateArg(
      extractToolArgument(argsPreview, "command") || summariseArgs(argsPreview),
      160,
    );
  }
  if (name === "code_run") {
    return truncateArg(
      extractToolArgument(argsPreview, "code") || summariseArgs(argsPreview),
      160,
    );
  }
  return summariseArgs(argsPreview);
}

function isShellLikeTool(name: string): boolean {
  return name === "shell" || name === "code_run";
}

function truncateArg(text: string, limit: number): string {
  const flat = text.replace(/\s+/g, " ").trim();
  return flat.length > limit ? `${flat.slice(0, limit - 1)}…` : flat;
}

function ResultBody({ text, isError }: { text: string; isError: boolean }): React.ReactElement {
  const lines = text.split("\n");
  return (
    <Box flexDirection="column">
      {lines.map((line, idx) => (
        <Box key={idx}>
          <Text color={THEME.subtle} dimColor>
            {idx === 0 ? "  ⎿  " : "     "}
          </Text>
          <Text color={isError ? THEME.error : THEME.subtle} dimColor={!isError}>
            {line}
          </Text>
        </Box>
      ))}
    </Box>
  );
}

function summariseArgs(preview: string): string {
  if (!preview) return "";
  const trimmed = preview
    .replace(/^\{|\}$/g, "")
    .replace(/"([^"]+)":/g, "$1=")
    .replace(/\s+/g, " ")
    .trim();
  return trimmed.length > 80 ? trimmed.slice(0, 79) + "…" : trimmed;
}
