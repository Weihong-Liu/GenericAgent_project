/**
 * Top-level Ink component.
 *
 * Owns the {@link GatewayClient}, drives the transcript reducer, and
 * composes the welcome page, transcript, slash overlay, multiline
 * input, history search, and status bar.
 */

import { Box, Text, useApp, useInput, useStdout } from "ink";
import React, {
  useCallback,
  useEffect,
  useMemo,
  useReducer,
  useRef,
  useState,
} from "react";

import { Welcome } from "./components/welcome.js";
import { BackgroundTasksDialog } from "./components/backgroundTasksDialog.js";
import { FileMentionOverlay } from "./components/fileMentionOverlay.js";
import { GlobalSearchDialog } from "./components/globalSearchDialog.js";
import { HistorySearchOverlay } from "./components/historySearchOverlay.js";
import { ModelPicker } from "./components/modelPicker.js";
import { QuickOpenDialog } from "./components/quickOpenDialog.js";
import { RateLimitOptions } from "./components/rateLimitOptions.js";
import { SandboxPermissionRequest } from "./components/sandboxPermissionRequest.js";
import { SessionBrowser, filterSessions } from "./components/sessionBrowser.js";
import { SlashOverlay } from "./components/slashOverlay.js";
import { StatusBar } from "./components/statusBar.js";
import {
  StatusNotices,
  buildStatusNotices,
} from "./components/statusNotices.js";
import { TextInput } from "./components/textInput.js";
import { ThemePicker } from "./components/themePicker.js";
import { ThinkingToggle } from "./components/thinkingToggle.js";
import { VirtualMessageList } from "./components/virtualMessageList.js";
import { VimTextInput } from "./components/vimTextInput.js";
import { WorktreeDialog } from "./components/worktreeDialog.js";
import { ApprovalPrompt } from "./components/approvalPrompt.js";
import { HelpOverlay } from "./components/helpOverlay.js";
import { MessageNavigator } from "./components/messageNavigator.js";
import { Notifications } from "./components/notifications.js";
import { PromptFooter } from "./components/promptInput/footer.js";
import {
  GatewayClient,
  GatewayError,
  GatewayProtocolError,
} from "./gatewayClient.js";
import { useInputHistory } from "./hooks/useInputHistory.js";
import { usePasteDetection } from "./hooks/usePasteDetection.js";
import { useStreamThrottle } from "./hooks/useStreamThrottle.js";
import {
  appendHistory,
  loadHistory,
} from "./persistence/historyFile.js";
import { applyCompletion, filterCommands } from "./state/commandFilter.js";
import { activeMention, applyMention, detectMode } from "./state/modeDetector.js";
import {
  initialNotifications,
  notificationsReducer,
} from "./state/notificationStore.js";
import {
  QueuedPrompt,
  initialPromptQueueState,
  promptQueueReducer,
} from "./state/promptQueue.js";
import {
  initialTranscriptState,
  transcriptReducer,
} from "./state/transcriptStore.js";
import type {
  ApprovalDecision,
  ApprovalRequestPayload,
  CommandDef,
  SessionSummary,
  BackgroundTask,
  RuntimeStatus,
  WorktreeStatusResult,
} from "./schemas.js";
import { approvalRequestPayloadSchema } from "./schemas.js";
import type { HistoryEntry } from "./hooks/useInputHistory.js";

interface AppProps {
  client: GatewayClient;
  initialStatus?: RuntimeStatus | undefined;
}

interface SubmitOptions {
  allowQueue?: boolean;
  commitHistory?: boolean;
}

export function App({ client, initialStatus }: AppProps): React.ReactElement {
  const { exit } = useApp();
  const { stdout } = useStdout();
  const [transcript, dispatch] = useReducer(transcriptReducer, initialTranscriptState);
  const [draft, setDraft] = useState("");
  const [status, setStatus] = useState<RuntimeStatus | null>(initialStatus ?? null);
  const [activeRequestId, setActiveRequestId] = useState<number | null>(null);
  const [terminalWidth, setTerminalWidth] = useState<number>(stdout?.columns ?? 80);
  const [terminalHeight, setTerminalHeight] = useState<number>(stdout?.rows ?? 24);
  const [commands, setCommands] = useState<readonly CommandDef[]>([]);
  const [selectedSuggestion, setSelectedSuggestion] = useState(0);
  const [historySearchOpen, setHistorySearchOpen] = useState(false);
  const [quickOpenOpen, setQuickOpenOpen] = useState(false);
  const [quickOpenQuery, setQuickOpenQuery] = useState("");
  const [quickOpenMatches, setQuickOpenMatches] = useState<readonly { path: string }[]>([]);
  const [quickOpenLoading, setQuickOpenLoading] = useState(false);
  const [globalSearchOpen, setGlobalSearchOpen] = useState(false);
  const [modelPickerOpen, setModelPickerOpen] = useState(false);
  const [themePickerOpen, setThemePickerOpen] = useState(false);
  const [themeName, setThemeName] = useState("default");
  const [thinkingToggleOpen, setThinkingToggleOpen] = useState(false);
  const [thinkingModeEnabled, setThinkingModeEnabled] = useState(false);
  const [sessionBrowserOpen, setSessionBrowserOpen] = useState(false);
  const [sessionBrowserQuery, setSessionBrowserQuery] = useState("");
  const [sessionBrowserIndex, setSessionBrowserIndex] = useState(0);
  const [sessionBrowserLoading, setSessionBrowserLoading] = useState(false);
  const [sessions, setSessions] = useState<readonly SessionSummary[]>([]);
  const [tasksDialogOpen, setTasksDialogOpen] = useState(false);
  const [tasksDialogLoading, setTasksDialogLoading] = useState(false);
  const [backgroundTasks, setBackgroundTasks] = useState<readonly BackgroundTask[]>([]);
  const [backgroundBusy, setBackgroundBusy] = useState(false);
  const [worktreeOpen, setWorktreeOpen] = useState(false);
  const [worktreeLoading, setWorktreeLoading] = useState(false);
  const [worktreeStatus, setWorktreeStatus] = useState<WorktreeStatusResult | null>(null);
  const [rateLimitOptionsOpen, setRateLimitOptionsOpen] = useState(false);
  const [dismissedStatusNotices, setDismissedStatusNotices] = useState<Set<string>>(
    () => new Set(),
  );
  const [navigatorOpen, setNavigatorOpen] = useState(false);
  const [navigatorIndex, setNavigatorIndex] = useState(0);
  const [transcriptMode, setTranscriptMode] = useState(false);
  const [showAllTranscript, setShowAllTranscript] = useState(false);
  const [pendingApproval, setPendingApproval] =
    useState<ApprovalRequestPayload | null>(null);
  const vimEnabled = useMemo(
    () => (process.env["GA_VIM_MODE"] ?? "").trim().length > 0,
    [],
  );
  const [vimMode, setVimMode] = useState<"insert" | "normal" | "visual" | "operator">(
    "normal",
  );
  const [helpOpen, setHelpOpen] = useState(false);
  const [notifications, dispatchNotification] = useReducer(
    notificationsReducer,
    initialNotifications,
  );
  const [promptQueue, dispatchPromptQueue] = useReducer(
    promptQueueReducer,
    initialPromptQueueState,
  );
  const promptQueueRef = useRef(initialPromptQueueState);
  const [stashedPrompt, setStashedPrompt] = useState<string | null>(null);
  const [fileMatches, setFileMatches] = useState<readonly { path: string }[]>([]);
  const [fileSelectedIndex, setFileSelectedIndex] = useState(0);
  const [fileLoading, setFileLoading] = useState(false);
  // History bootstrapped from the GenericAgent config dir's history.jsonl.
  const initialHistory = useMemo<HistoryEntry[]>(() => loadHistory(), []);
  const history = useInputHistory({
    initial: initialHistory,
    onCommit: (entry) => appendHistory(entry),
  });
  const paste = usePasteDetection();
  // Mirror activeRequestId in a ref so the Ctrl-C handler reads the current
  // value synchronously rather than waiting for a React re-render.
  const activeRequestRef = useRef<number | null>(null);
  /**
   * Wall-clock when the current turn began. Used by the phantom
   * ThinkingIndicator that renders before the assistant bubble or any
   * tool_call has appeared in the transcript. ``null`` between turns.
   */
  const [turnStartedAt, setTurnStartedAt] = useState<number | null>(null);
  // Snapshot of all entries committed to the history hook for the search
  // overlay. We rebuild it via a small ref + state so the overlay re-renders
  // on commit without subscribing to the hook's internal state.
  const [historySnapshot, setHistorySnapshot] = useState<HistoryEntry[]>(initialHistory);

  // 60Hz throttle for content_delta — merges multiple per-token deltas
  // arriving in the same frame into a single transcript reducer dispatch.
  // Tool events and lifecycle events stay on the synchronous path because
  // the user expects them to appear immediately.
  const lastDeltaRequestId = useRef<number | null>(null);
  const streamThrottle = useStreamThrottle({
    onFlush: (mergedDelta) => {
      const requestId = lastDeltaRequestId.current;
      if (requestId === null) return;
      dispatch({
        type: "event",
        frame: {
          type: "event",
          kind: "content_delta",
          payload: { kind: "content_delta", delta: mergedDelta },
          request_id: requestId,
        },
      });
    },
  });
  const submitCoreRef = useRef<
    ((line: string, options?: SubmitOptions) => Promise<void>) | null
  >(null);

  useEffect(() => {
    promptQueueRef.current = promptQueue;
  }, [promptQueue]);

  const enqueueQueuedPrompt = useCallback((text: string): void => {
    const trimmed = text.trim();
    if (!trimmed) return;
    const action = { type: "enqueue" as const, text: trimmed };
    promptQueueRef.current = promptQueueReducer(promptQueueRef.current, action);
    dispatchPromptQueue(action);
    dispatchNotification({
      type: "push",
      level: "info",
      message: `queued: ${oneLine(trimmed, 48)}`,
    });
  }, []);

  const shiftQueuedPrompt = useCallback((): QueuedPrompt | null => {
    const next = promptQueueRef.current.prompts[0] ?? null;
    if (!next) return null;
    const action = { type: "dequeue" as const };
    promptQueueRef.current = promptQueueReducer(promptQueueRef.current, action);
    dispatchPromptQueue(action);
    return next;
  }, []);

  const scheduleNextQueuedPrompt = useCallback((): void => {
    const next = shiftQueuedPrompt();
    if (!next) return;
    setTimeout(() => {
      void submitCoreRef.current?.(next.text, {
        allowQueue: false,
        commitHistory: false,
      });
    }, 0);
  }, [shiftQueuedPrompt]);

  // Subscribe to streaming events from the backend.
  useEffect(() => {
    const offDelta = client.on("content_delta", (frame) => {
      lastDeltaRequestId.current = frame.request_id ?? null;
      const delta = typeof frame.payload.delta === "string" ? frame.payload.delta : "";
      streamThrottle.push(delta);
    });
    const offToolCall = client.on("tool_call", (frame) => {
      streamThrottle.flush();
      dispatch({ type: "event", frame });
    });
    const offToolResult = client.on("tool_result", (frame) => {
      streamThrottle.flush();
      dispatch({ type: "event", frame });
    });
    const offError = client.on("error", (frame) => {
      streamThrottle.flush();
      dispatch({ type: "event", frame });
    });
    const offStopped = client.on("loop_stopped", (frame) => {
      streamThrottle.flush();
      dispatch({ type: "event", frame });
    });
    const offMessageDone = client.on("message_done", () => streamThrottle.flush());
    const offTurnFinished = client.on("turn_finished", () => streamThrottle.flush());
    const offApproval = client.on("approval_request", (frame) => {
      const parsed = approvalRequestPayloadSchema.safeParse(frame.payload);
      if (parsed.success) setPendingApproval(parsed.data);
    });

    return () => {
      offDelta();
      offToolCall();
      offToolResult();
      offError();
      offStopped();
      offMessageDone();
      offTurnFinished();
      offApproval();
    };
  }, [client, streamThrottle]);

  useEffect(() => {
    if (initialStatus) return;
    client.runtimeStatus().then(setStatus).catch(() => {});
  }, [client, initialStatus]);

  useEffect(() => {
    let cancelled = false;
    client
      .commandsList()
      .then((res) => {
        if (!cancelled) setCommands(res.commands);
      })
      .catch((exc: unknown) => {
        if (cancelled) return;
        dispatch({
          type: "command_output",
          content: `slash-command catalogue unavailable (${formatError(exc)})`,
          is_error: true,
        });
      });
    return () => {
      cancelled = true;
    };
  }, [client]);

  // GC expired notifications every 250ms.
  useEffect(() => {
    const handle = setInterval(() => {
      dispatchNotification({ type: "expire", now: Date.now() });
    }, 250);
    return () => clearInterval(handle);
  }, []);

  useEffect(() => {
    if (!stdout || typeof stdout.on !== "function") return;
    const onResize = (): void => {
      setTerminalWidth(stdout.columns ?? 80);
      setTerminalHeight(stdout.rows ?? 24);
    };
    stdout.on("resize", onResize);
    return () => {
      if (typeof stdout.off === "function") stdout.off("resize", onResize);
    };
  }, [stdout]);

  const inputMode = detectMode(draft, draft.length);
  const matches = inputMode === "slash" ? filterCommands(commands, draft) : [];
  const slashOverlayActive = matches.length > 0 && !historySearchOpen;
  const mentionToken = activeMention(draft, draft.length);
  const mentionOverlayActive =
    inputMode === "mention" && mentionToken !== null && !historySearchOpen;
  const matchesKey = matches.map((m) => m.name).join("|");
  const pickerOpen =
    historySearchOpen ||
    quickOpenOpen ||
    globalSearchOpen ||
    modelPickerOpen ||
    themePickerOpen ||
    thinkingToggleOpen ||
    sessionBrowserOpen ||
    tasksDialogOpen ||
    worktreeOpen ||
    rateLimitOptionsOpen;

  const statusNotices = useMemo(
    () => buildStatusNotices(status, dismissedStatusNotices),
    [dismissedStatusNotices, status],
  );

  useEffect(() => {
    setSelectedSuggestion(0);
  }, [matchesKey]);

  // Debounced file search whenever the active mention query changes.
  useEffect(() => {
    if (!mentionOverlayActive || !mentionToken) {
      setFileMatches([]);
      setFileLoading(false);
      return;
    }
    const query = mentionToken.query;
    let cancelled = false;
    setFileLoading(true);
    const handle = setTimeout(() => {
      client
        .filesSearch(query, 25)
        .then((res) => {
          if (cancelled) return;
          setFileMatches(res.matches);
          setFileSelectedIndex(0);
          setFileLoading(false);
        })
        .catch(() => {
          if (cancelled) return;
          setFileMatches([]);
          setFileLoading(false);
        });
    }, 80);
    return () => {
      cancelled = true;
      clearTimeout(handle);
    };
  }, [client, mentionOverlayActive, mentionToken?.query]);

  useEffect(() => {
    if (!quickOpenOpen) {
      setQuickOpenMatches([]);
      setQuickOpenLoading(false);
      return;
    }
    let cancelled = false;
    setQuickOpenLoading(true);
    const handle = setTimeout(() => {
      client
        .filesSearch(quickOpenQuery, 40)
        .then((res) => {
          if (cancelled) return;
          setQuickOpenMatches(res.matches);
          setQuickOpenLoading(false);
        })
        .catch(() => {
          if (cancelled) return;
          setQuickOpenMatches([]);
          setQuickOpenLoading(false);
        });
    }, 80);
    return () => {
      cancelled = true;
      clearTimeout(handle);
    };
  }, [client, quickOpenOpen, quickOpenQuery]);

  const filteredSessions = useMemo(
    () => filterSessions(sessions, sessionBrowserQuery),
    [sessions, sessionBrowserQuery],
  );

  const openSessionBrowser = useCallback((): void => {
    setSessionBrowserQuery("");
    setSessionBrowserIndex(0);
    setSessionBrowserOpen(true);
    setSessionBrowserLoading(true);
    client
      .sessionList()
      .then((res) => {
        setSessions(res.sessions);
        setSessionBrowserLoading(false);
      })
      .catch((exc: unknown) => {
        setSessions([]);
        setSessionBrowserLoading(false);
        dispatchNotification({
          type: "push",
          level: "error",
          message: `sessions unavailable: ${formatError(exc)}`,
        });
      });
  }, [client]);

  const openTasksDialog = useCallback((): void => {
    setTasksDialogOpen(true);
    setTasksDialogLoading(true);
    client
      .tasksList()
      .then((res) => {
        setBackgroundTasks(res.tasks);
        setBackgroundBusy(res.busy);
        setTasksDialogLoading(false);
      })
      .catch((exc: unknown) => {
        setBackgroundTasks([]);
        setBackgroundBusy(false);
        setTasksDialogLoading(false);
        dispatchNotification({
          type: "push",
          level: "error",
          message: `tasks unavailable: ${formatError(exc)}`,
        });
      });
  }, [client]);

  const openWorktreeDialog = useCallback((): void => {
    setWorktreeOpen(true);
    setWorktreeLoading(true);
    client
      .worktreeStatus()
      .then((res) => {
        setWorktreeStatus(res);
        setWorktreeLoading(false);
      })
      .catch((exc: unknown) => {
        setWorktreeStatus(null);
        setWorktreeLoading(false);
        dispatchNotification({
          type: "push",
          level: "error",
          message: `worktree unavailable: ${formatError(exc)}`,
        });
      });
  }, [client]);

  // Top-level keys: Ctrl-C, Tab/arrow nav for slash overlay, Ctrl-R search.
  useInput((input, key) => {
    if (key.ctrl && input === "c") {
      if (activeRequestRef.current !== null) {
        client.chatCancel(activeRequestRef.current).catch(() => {});
      } else {
        client.shutdown().finally(() => exit());
      }
      return;
    }

    if (key.ctrl && input === "r" && !historySearchOpen) {
      setHistorySearchOpen(true);
      return;
    }

    if (key.ctrl && input === "n" && statusNotices.length > 0) {
      const first = statusNotices[0];
      if (first) {
        setDismissedStatusNotices((prev) => new Set([...prev, first.id]));
      }
      return;
    }

    if (key.ctrl && input === "o") {
      setTranscriptMode((enabled) => {
        const next = !enabled;
        if (!next) setShowAllTranscript(false);
        return next;
      });
      return;
    }

    if (key.ctrl && input === "e") {
      setTranscriptMode(true);
      setShowAllTranscript((enabled) => !enabled);
      return;
    }

    if (rateLimitOptionsOpen) {
      if (key.escape || input === "q") {
        setRateLimitOptionsOpen(false);
      }
      return;
    }

    if (sessionBrowserOpen) {
      if (key.escape) {
        setSessionBrowserOpen(false);
        return;
      }
      if (key.upArrow) {
        setSessionBrowserIndex((idx) =>
          Math.max(0, Math.min(filteredSessions.length - 1, idx - 1)),
        );
        return;
      }
      if (key.downArrow) {
        setSessionBrowserIndex((idx) =>
          Math.max(0, Math.min(filteredSessions.length - 1, idx + 1)),
        );
        return;
      }
      if (key.return) {
        const picked = filteredSessions[sessionBrowserIndex] ?? filteredSessions[0];
        if (picked) {
          client
            .sessionResume(picked.id)
            .then((res) => {
              setStatus((prev) =>
                prev
                  ? { ...prev, session_id: res.session_id, turn_count: res.turn_count }
                  : prev,
              );
              setSessionBrowserOpen(false);
              dispatch({
                type: "command_output",
                content: `Resumed session: ${res.session_id}`,
                is_error: false,
              });
            })
            .catch((exc: unknown) => {
              dispatchNotification({
                type: "push",
                level: "error",
                message: `resume failed: ${formatError(exc)}`,
              });
            });
        }
        return;
      }
      if (key.backspace || key.delete) {
        setSessionBrowserQuery((query) => query.slice(0, -1));
        setSessionBrowserIndex(0);
        return;
      }
      if (input && !key.ctrl && !key.meta) {
        setSessionBrowserQuery((query) => query + input);
        setSessionBrowserIndex(0);
        return;
      }
      return;
    }

    if (tasksDialogOpen || worktreeOpen) {
      if (key.escape || key.return) {
        setTasksDialogOpen(false);
        setWorktreeOpen(false);
      }
      return;
    }

    if (!pickerOpen && key.ctrl && input === "p") {
      setQuickOpenQuery("");
      setQuickOpenOpen(true);
      return;
    }

    if (!pickerOpen && key.ctrl && input === "f") {
      setGlobalSearchOpen(true);
      return;
    }

    if (!pickerOpen && key.ctrl && input === "m") {
      setModelPickerOpen(true);
      return;
    }

    if (!pickerOpen && key.ctrl && input === "t") {
      setThemePickerOpen(true);
      return;
    }

    if (!pickerOpen && key.ctrl && input === "x") {
      setThinkingToggleOpen(true);
      return;
    }

    if (!pickerOpen && key.ctrl && input === "s") {
      openSessionBrowser();
      return;
    }

    if (!pickerOpen && key.ctrl && input === "b") {
      openTasksDialog();
      return;
    }

    if (!pickerOpen && key.ctrl && input === "j") {
      openWorktreeDialog();
      return;
    }

    if (key.ctrl && input === "g") {
      // Ctrl-G interrupts the running turn — same as the first Ctrl-C
      // press but never exits the app.
      if (activeRequestRef.current !== null) {
        if (draft.trim()) {
          setStashedPrompt(draft);
          setDraft("");
        }
        client.chatCancel(activeRequestRef.current).catch(() => {});
        dispatchNotification({
          type: "push",
          level: "warn",
          message: "turn cancelled",
        });
      }
      return;
    }

    if (key.ctrl && input === "y" && stashedPrompt !== null && draft.length === 0) {
      setDraft(stashedPrompt);
      setStashedPrompt(null);
      dispatchNotification({
        type: "push",
        level: "info",
        message: "restored stashed prompt",
      });
      return;
    }

    if (pickerOpen) return;

    if (key.ctrl && input === "l") {
      // Ctrl-L clears the visible transcript without ending the
      // session. The reducer doesn't expose a "clear" action yet so
      // we restart it via session.new which keeps the conversation
      // history server-side but resets the visible items.
      client
        .sessionNew()
        .then(() => {
          dispatchNotification({
            type: "push",
            level: "info",
            message: "transcript cleared",
          });
        })
        .catch(() => {});
      return;
    }

    if (key.ctrl && input === "d" && draft.length === 0) {
      // Ctrl-D on an empty input exits cleanly.
      client.shutdown().finally(() => exit());
      return;
    }

    if (input === "?" && draft.length === 0 && !helpOpen) {
      setHelpOpen(true);
      return;
    }

    // Shift-↑ enters the read-only message navigator. Esc exits.
    if (
      !navigatorOpen &&
      !historySearchOpen &&
      !slashOverlayActive &&
      !mentionOverlayActive &&
      key.shift &&
      key.upArrow &&
      transcript.items.length > 0
    ) {
      setNavigatorIndex(transcript.items.length - 1);
      setNavigatorOpen(true);
      return;
    }
    if (navigatorOpen) {
      if (key.escape) {
        setNavigatorOpen(false);
        return;
      }
      if (key.upArrow) {
        setNavigatorIndex((idx) => Math.max(0, idx - 1));
        return;
      }
      if (key.downArrow) {
        setNavigatorIndex((idx) =>
          Math.min(transcript.items.length - 1, idx + 1),
        );
        return;
      }
      if (input === " ") {
        const item = transcript.items[navigatorIndex];
        if (item && item.kind === "tool") {
          dispatch({ type: "toggle_tool", tool_use_id: item.tool_use_id });
        }
        return;
      }
      // While navigator is up, swallow other keys so the input box
      // does not consume them.
      return;
    }

    if (slashOverlayActive) {
      if (key.upArrow) {
        setSelectedSuggestion((idx) => (idx - 1 + matches.length) % matches.length);
        return;
      }
      if (key.downArrow) {
        setSelectedSuggestion((idx) => (idx + 1) % matches.length);
        return;
      }
      if (key.tab) {
        const pick = matches[selectedSuggestion] ?? matches[0];
        if (pick) setDraft(applyCompletion(pick));
        return;
      }
    }

    if (mentionOverlayActive) {
      if (key.upArrow) {
        setFileSelectedIndex((idx) => Math.max(0, idx - 1));
        return;
      }
      if (key.downArrow) {
        setFileSelectedIndex((idx) =>
          Math.min(Math.max(0, fileMatches.length - 1), idx + 1),
        );
        return;
      }
      if (key.tab || key.return) {
        const pick = fileMatches[fileSelectedIndex] ?? fileMatches[0];
        if (pick) {
          const applied = applyMention(draft, draft.length, pick.path);
          setDraft(applied.value);
        }
        return;
      }
      if (key.escape) {
        // Drop the @ token so the overlay closes; user can keep typing.
        if (mentionToken) {
          setDraft(draft.slice(0, mentionToken.start) + draft.slice(mentionToken.end));
        }
        return;
      }
    }
  });

  const submitCore = useCallback(
    async (line: string, options: SubmitOptions = {}) => {
      const allowQueue = options.allowQueue ?? true;
      const commitHistory = options.commitHistory ?? true;
      const text = line.trim();
      if (!text) return;
      setDraft("");
      if (allowQueue && activeRequestRef.current !== null) {
        if (commitHistory) {
          const queuedMode: "chat" | "bash" = text.startsWith("!") ? "bash" : "chat";
          history.commit({ mode: queuedMode, text });
          setHistorySnapshot((prev) => [...prev, { mode: queuedMode, text }]);
          history.reset();
        }
        enqueueQueuedPrompt(text);
        return;
      }
      // Persist to history under the right mode. Bash entries (!) live
      // in their own stack so up-arrow recall is consistent with what
      // the user typed.
      const submittedMode: "chat" | "bash" = text.startsWith("!") ? "bash" : "chat";
      if (commitHistory) {
        history.commit({ mode: submittedMode, text });
        setHistorySnapshot((prev) => [...prev, { mode: submittedMode, text }]);
        history.reset();
      }

      if (text.startsWith("/")) {
        if (text === "/rate-limit-options") {
          setRateLimitOptionsOpen(true);
          scheduleNextQueuedPrompt();
          return;
        }
        dispatch({ type: "user_input", text });
        try {
          const result = await client.commandsDispatch(text);
          dispatch({
            type: "command_output",
            content: result.content,
            is_error: result.is_error,
          });
          if (result.should_exit) {
            await client.shutdown();
            exit();
          }
        } catch (exc) {
          dispatch({
            type: "command_output",
            content: formatError(exc),
            is_error: true,
          });
        } finally {
          scheduleNextQueuedPrompt();
        }
        return;
      }

      if (text.startsWith("!")) {
        const command = text.slice(1).trim();
        if (!command) return;
        dispatch({ type: "user_input", text });
        try {
          const result = await client.toolsRun("shell", { command });
          dispatch({
            type: "command_output",
            content: result.content,
            is_error: result.is_error,
          });
        } catch (exc) {
          dispatch({
            type: "command_output",
            content: formatError(exc),
            is_error: true,
          });
        } finally {
          scheduleNextQueuedPrompt();
        }
        return;
      }

      dispatch({ type: "user_input", text });
      const { id, result } = client.chatSend(text);
      activeRequestRef.current = id;
      setActiveRequestId(id);
      setTurnStartedAt(Date.now());
      dispatch({ type: "begin_turn", request_id: id });

      try {
        const final = await result;
        dispatch({ type: "end_turn", request_id: id, final_text: final.content });
        if (final.is_error) {
          dispatch({
            type: "command_output",
            content: `${final.error_type ?? "error"}: ${final.content}`,
            is_error: true,
          });
        }
      } catch (exc) {
        dispatch({ type: "end_turn", request_id: id, final_text: "" });
        dispatch({ type: "command_output", content: formatError(exc), is_error: true });
      } finally {
        activeRequestRef.current = null;
        setActiveRequestId(null);
        setTurnStartedAt(null);
        client.runtimeStatus().then(setStatus).catch(() => {});
        scheduleNextQueuedPrompt();
      }
    },
    [client, enqueueQueuedPrompt, exit, history, scheduleNextQueuedPrompt],
  );
  submitCoreRef.current = submitCore;
  const submit = useCallback(
    async (line: string) => submitCore(line, { allowQueue: true, commitHistory: true }),
    [submitCore],
  );

  const prefixGlyph =
    activeRequestId !== null
      ? "··· "
      : inputMode === "bash"
        ? "! "
        : inputMode === "mention"
          ? "@ "
          : "❯ ";
  const prefixColor =
    activeRequestId !== null
      ? "gray"
      : inputMode === "bash"
        ? "yellow"
        : inputMode === "mention"
          ? "magenta"
          : "cyan";
  const historyMode = inputMode === "bash" ? "bash" : "chat";
  const messageWindowRows = Math.max(8, terminalHeight - 12);

  return (
    <Box flexDirection="column">
      <Welcome width={terminalWidth} status={status} />{/* width retained for future responsive tweaks */}
      <StatusNotices
        notices={statusNotices}
        onDismiss={(id) => setDismissedStatusNotices((prev) => new Set([...prev, id]))}
      />
      <VirtualMessageList
        items={transcript.items}
        activeRequestId={activeRequestId}
        turnStartedAt={turnStartedAt}
        maxRows={messageWindowRows}
        selectedIndex={navigatorOpen ? navigatorIndex : null}
        transcriptMode={transcriptMode}
        showAll={showAllTranscript}
      />
      <SlashOverlay matches={matches} selectedIndex={selectedSuggestion} />
      {mentionOverlayActive ? (
        <FileMentionOverlay
          matches={fileMatches}
          selectedIndex={fileSelectedIndex}
          query={mentionToken?.query ?? ""}
          loading={fileLoading}
        />
      ) : null}
      {quickOpenOpen ? (
        <QuickOpenDialog
          matches={quickOpenMatches}
          loading={quickOpenLoading}
          onQueryChange={setQuickOpenQuery}
          onSelect={(path) => {
            setDraft((prev) => `${prev}${prev && !prev.endsWith(" ") ? " " : ""}@${path} `);
            setQuickOpenOpen(false);
          }}
          onCancel={() => setQuickOpenOpen(false)}
        />
      ) : null}
      {globalSearchOpen ? (
        <GlobalSearchDialog
          items={transcript.items}
          onSelect={(index) => {
            setNavigatorIndex(index);
            setNavigatorOpen(true);
            setGlobalSearchOpen(false);
          }}
          onCancel={() => setGlobalSearchOpen(false)}
        />
      ) : null}
      {modelPickerOpen ? (
        <ModelPicker
          currentModel={status?.model ?? ""}
          onSelectCurrent={() => {
            setModelPickerOpen(false);
            dispatchNotification({
              type: "push",
              level: "info",
              message: "model unchanged",
            });
          }}
          onCancel={() => setModelPickerOpen(false)}
        />
      ) : null}
      {themePickerOpen ? (
        <ThemePicker
          currentTheme={themeName}
          onSelect={(theme) => {
            if (theme === "custom") {
              dispatchNotification({
                type: "push",
                level: "warn",
                message: "custom themes are not wired yet",
              });
            } else {
              setThemeName(theme);
              dispatchNotification({
                type: "push",
                level: "info",
                message: `theme: ${theme}`,
              });
            }
            setThemePickerOpen(false);
          }}
          onCancel={() => setThemePickerOpen(false)}
        />
      ) : null}
      {thinkingToggleOpen ? (
        <ThinkingToggle
          enabled={thinkingModeEnabled}
          onToggle={() => {
            setThinkingModeEnabled((enabled) => !enabled);
            setThinkingToggleOpen(false);
            dispatchNotification({
              type: "push",
              level: "info",
              message: "thinking marker toggled",
            });
          }}
          onCancel={() => setThinkingToggleOpen(false)}
        />
      ) : null}
      {sessionBrowserOpen ? (
        <SessionBrowser
          sessions={sessions}
          query={sessionBrowserQuery}
          selectedIndex={sessionBrowserIndex}
          loading={sessionBrowserLoading}
        />
      ) : null}
      {tasksDialogOpen ? (
        <BackgroundTasksDialog
          tasks={backgroundTasks}
          busy={backgroundBusy}
          loading={tasksDialogLoading}
        />
      ) : null}
      {worktreeOpen ? (
        <WorktreeDialog status={worktreeStatus} loading={worktreeLoading} />
      ) : null}
      {rateLimitOptionsOpen ? <RateLimitOptions status={status} /> : null}
      {status !== null ? (
        <SandboxPermissionRequest mode={envTruthy(process.env["GA_YOLO"]) ? "bypass" : "approval-required"} />
      ) : null}
      {navigatorOpen ? (
        <MessageNavigator
          items={transcript.items}
          selectedIndex={navigatorIndex}
          maxRows={messageWindowRows}
        />
      ) : null}
      <Notifications items={notifications.items} />
      {helpOpen ? <HelpOverlay onClose={() => setHelpOpen(false)} /> : null}
      {pendingApproval !== null ? (
        <ApprovalPrompt
          toolName={pendingApproval.name}
          argumentsPreview={pendingApproval.arguments_preview}
          onDecide={(decision: ApprovalDecision) => {
            const target = pendingApproval;
            setPendingApproval(null);
            client.chatApprove(target.tool_use_id, decision).catch(() => {});
          }}
        />
      ) : null}
      {historySearchOpen ? (
        <HistorySearchOverlay
          history={historySnapshot}
          mode={historyMode}
          onSelect={(text) => {
            setDraft(text);
            setHistorySearchOpen(false);
          }}
          onCancel={() => setHistorySearchOpen(false)}
        />
      ) : helpOpen ? null : (
        <PromptFooter
          mode={inputMode}
          busy={activeRequestId !== null}
          queued={promptQueue.prompts}
          stashedPrompt={stashedPrompt}
        />
      )}
      {historySearchOpen || helpOpen ? null : vimEnabled ? (
        <VimTextInput
          value={draft}
          onChange={setDraft}
          onSubmit={submit}
          focus={
            !slashOverlayActive &&
            !mentionOverlayActive &&
            !pickerOpen &&
            !navigatorOpen &&
            pendingApproval === null
          }
          placeholder="vim mode (Esc=NORMAL, i=INSERT)"
          prefix={<Text color={prefixColor}>{prefixGlyph}</Text>}
          onModeChange={setVimMode}
        />
      ) : (
        <TextInput
          value={draft}
          onChange={setDraft}
          onSubmit={submit}
          focus={!pickerOpen && !navigatorOpen && pendingApproval === null}
          disableNavigation={
            slashOverlayActive ||
            mentionOverlayActive ||
            pickerOpen ||
            navigatorOpen ||
            pendingApproval !== null
          }
          placeholder="type a message; / commands, ! shell, @ files, Ctrl-R history, Ctrl-S sessions"
          prefix={<Text color={prefixColor}>{prefixGlyph}</Text>}
          onHistoryUp={(current) => history.prev(historyMode, current)}
          onHistoryDown={(current) => history.next(historyMode, current)}
          isPasting={paste.isPasting}
          observePaste={(chunk) => {
            paste.observe(chunk);
          }}
        />
      )}
      <StatusBar
        status={status}
        busy={activeRequestId !== null}
        vimMode={vimEnabled ? vimMode : null}
        transcriptMode={transcriptMode}
        showAll={showAllTranscript}
        width={terminalWidth}
      />
    </Box>
  );
}

function oneLine(text: string, limit: number): string {
  const flat = text.replace(/\s+/g, " ").trim();
  return flat.length > limit ? flat.slice(0, Math.max(0, limit - 1)) + "…" : flat;
}

function envTruthy(value: string | undefined): boolean {
  return ["1", "true", "yes", "on"].includes((value ?? "").trim().toLowerCase());
}

function formatError(exc: unknown): string {
  if (exc instanceof GatewayError) return `[${exc.code}] ${exc.message}`;
  if (exc instanceof GatewayProtocolError) return `protocol error: ${exc.message}`;
  if (exc instanceof Error) return exc.message;
  return String(exc);
}
