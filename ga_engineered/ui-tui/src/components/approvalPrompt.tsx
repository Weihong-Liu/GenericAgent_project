/**
 * Inline approval widget shown when the gateway pauses on a high-risk
 * tool. Captures a single keystroke (y/Y, n/N, a/A, Esc) and dispatches
 * the matching ``chat.approve`` decision via the parent.
 */

import React from "react";

import type { ApprovalDecision } from "../schemas.js";
import { PermissionRequest } from "./permissionRequest.js";

export interface ApprovalPromptProps {
  toolName: string;
  argumentsPreview: string;
  onDecide: (decision: ApprovalDecision) => void;
}

export function ApprovalPrompt({
  toolName,
  argumentsPreview,
  onDecide,
}: ApprovalPromptProps): React.ReactElement {
  return (
    <PermissionRequest
      toolName={toolName}
      argumentsPreview={argumentsPreview}
      onDecide={onDecide}
    />
  );
}
