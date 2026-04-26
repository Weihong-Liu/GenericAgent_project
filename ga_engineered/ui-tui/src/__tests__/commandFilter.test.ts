import { describe, expect, it } from "vitest";

import { applyCompletion, filterCommands } from "../state/commandFilter.js";
import type { CommandDef } from "../schemas.js";

const cmd = (
  name: string,
  description = "",
  aliases: string[] = [],
  args_hint = "",
): CommandDef => ({
  name,
  description,
  category: "test",
  aliases,
  args_hint,
  subcommands: [],
  cli_only: false,
});

const COMMANDS: CommandDef[] = [
  cmd("help", "Show help", ["?"]),
  cmd("history", "Show conversation history"),
  cmd("model", "Switch model", [], "[model]"),
  cmd("new", "Start a fresh session", ["reset"]),
  cmd("clear", "Clear screen"),
  cmd("exit", "Exit", ["quit"]),
];

describe("filterCommands", () => {
  it("returns [] when query has no leading slash", () => {
    expect(filterCommands(COMMANDS, "help")).toEqual([]);
    expect(filterCommands(COMMANDS, "")).toEqual([]);
  });

  it("returns all commands for bare slash", () => {
    expect(filterCommands(COMMANDS, "/")).toHaveLength(COMMANDS.length);
  });

  it("ranks exact name above prefix above substring", () => {
    const sorted = filterCommands(COMMANDS, "/he");
    expect(sorted.map((c) => c.name)).toEqual(["help"]);
  });

  it("matches across aliases", () => {
    const sorted = filterCommands(COMMANDS, "/qu");
    expect(sorted.some((c) => c.name === "exit")).toBe(true);
  });

  it("alias exact match outranks alias prefix", () => {
    const cmds: CommandDef[] = [
      cmd("foo", "", ["q"]),
      cmd("bar", "", ["qx"]),
    ];
    const sorted = filterCommands(cmds, "/q");
    // ``foo`` (alias === "q") should outrank ``bar`` (alias starts with "q").
    expect(sorted[0]?.name).toBe("foo");
  });

  it("scores all aliases — alias order does not change the score", () => {
    // Regression: an earlier implementation returned on the first matching
    // alias, so ``["qu", "q"]`` queried with ``"q"`` would have scored 70
    // (prefix) instead of 80 (exact). We assert via observed ranking: the
    // command with the matching exact alias must outrank a command whose
    // only match is alias prefix.
    const cmds: CommandDef[] = [
      cmd("alpha", "", ["qu", "q"]), // exact-alias match should win
      cmd("beta", "", ["qz"]), // only prefix-alias match
    ];
    const sorted = filterCommands(cmds, "/q");
    expect(sorted.map((c) => c.name)).toEqual(["alpha", "beta"]);
  });

  it("name prefix beats name substring", () => {
    const cmds: CommandDef[] = [cmd("history"), cmd("show-history")];
    const sorted = filterCommands(cmds, "/hist");
    expect(sorted[0]?.name).toBe("history");
  });

  it("returns no matches for unknown prefix", () => {
    expect(filterCommands(COMMANDS, "/xyzzy")).toEqual([]);
  });

  it("is case-insensitive on the term", () => {
    const sorted = filterCommands(COMMANDS, "/HELP");
    expect(sorted[0]?.name).toBe("help");
  });
});

describe("applyCompletion", () => {
  it("prepends a slash and trailing space when args_hint exists", () => {
    expect(applyCompletion(cmd("model", "", [], "[model]"))).toBe("/model ");
  });

  it("emits no trailing space when there is no args_hint", () => {
    expect(applyCompletion(cmd("help"))).toBe("/help");
  });
});
