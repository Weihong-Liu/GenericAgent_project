# Keyboard Shortcuts

Type `?` (with empty input) or `/shortcuts` inside the TUI to see this
list. Anything outside the input box ignores keystrokes; everything
listed here works while the input is focused.

## Submission and editing

| Keys | Effect |
|---|---|
| `Enter` | submit |
| `Shift-Enter` / `Alt-Enter` | insert a newline |
| `Backspace` | delete char to the left of the cursor |
| `Ctrl-W` | delete previous word |
| `Ctrl-U` | kill to start of current line |
| `Ctrl-K` | kill to end of current line |
| `Ctrl-A` / `Home` | jump to start of current line |
| `Ctrl-E` / `End` | jump to end of current line |
| `← / →` | move cursor by character |
| `Ctrl-← / Ctrl-→` | jump cursor by word |

## History

| Keys | Effect |
|---|---|
| `↑` (top line) | recall previous prompt |
| `↓` (bottom line) | recall next prompt; restore draft when past the end |
| `Ctrl-R` | open full-history fuzzy search |

## Mode prefixes

| Keys | Effect |
|---|---|
| `/<command>` | slash command palette (Tab to accept, ↑↓ to navigate) |
| `!<cmd>` | run shell directly via `tools.run` (no LLM turn) |
| `@<query>` | fuzzy file picker (Tab to insert path) |

## Transcript

| Keys | Effect |
|---|---|
| `Shift-↑` | open message navigator |
| `↑` / `↓` (in navigator) | move selection |
| `Space` (in navigator) | expand / collapse the selected tool result |
| `Esc` (in navigator) | return to input |

## Approval

| Keys | Effect (only while an approval prompt is open) |
|---|---|
| `y` / `Y` / `Enter` | allow this call once |
| `n` / `N` / `Esc` | deny |
| `a` / `A` | always allow this tool (persisted to `$GENERIC_AGENT_HOME/approvals.json`) |

## Session

| Keys | Effect |
|---|---|
| `Ctrl-G` | interrupt the running turn (no exit) |
| `Ctrl-L` | clear the visible transcript (server keeps history) |
| `Ctrl-C` | first press cancels the in-flight turn; second press exits |
| `Ctrl-D` (empty input) | exit |
| `?` (empty input) or `/shortcuts` | show this help overlay |

## Vim mode (optional, opt in via `GA_VIM_MODE=1`)

| Mode | Keys | Effect |
|---|---|---|
| NORMAL | `i / I / a / A / o / O` | enter INSERT mode |
| NORMAL | `v` | enter VISUAL mode |
| NORMAL | `h j k l` | move cursor |
| NORMAL | `w / b` | jump by word |
| NORMAL | `0 / $ / ^` | line start / end |
| NORMAL | `gg / G` | buffer start / end |
| NORMAL | `x` | delete char under cursor |
| NORMAL | `d{motion}` / `dd` | delete |
| NORMAL | `c{motion}` / `cc` | change (delete then INSERT) |
| NORMAL | `y{motion}` / `yy` | yank into the register |
| NORMAL | `u` | undo last change |
| INSERT | any printable | insert at cursor |
| INSERT | `Esc` | return to NORMAL |
| VISUAL | `d / c / y` | apply operator to selection |
| VISUAL | `Esc` / `v` | cancel selection |
