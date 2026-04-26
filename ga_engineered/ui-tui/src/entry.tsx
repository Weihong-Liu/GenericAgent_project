#!/usr/bin/env node
/**
 * Entry point invoked by the Python launcher (and by ``npm run dev``).
 *
 * Boots the GatewayClient, waits for the backend's ``gateway.ready``
 * event, fetches initial runtime.status, then renders the Ink app.
 */

import { render } from "ink";
import React from "react";

import { App } from "./App.js";
import {
  GatewayClient,
  GatewayError,
  GatewayProtocolError,
} from "./gatewayClient.js";

async function main(): Promise<void> {
  const command = process.env["GA_GATEWAY_PYTHON"] ?? "python3";
  const argv = process.env["GA_GATEWAY_MODULE"]
    ? ["-m", process.env["GA_GATEWAY_MODULE"] as string]
    : ["-m", "generic_agent_engineered.gateway"];

  const client = new GatewayClient({ command, args: argv });

  try {
    await client.ready();
  } catch (exc) {
    process.stderr.write(formatError(exc) + "\n");
    if (client.stderr().length > 0) {
      process.stderr.write("--- gateway stderr ---\n");
      process.stderr.write(client.stderr());
    }
    // Do not leak the Python child if ready() failed mid-handshake.
    await client.shutdown().catch(() => {});
    process.exit(1);
  }

  const initialStatus = await client.runtimeStatus().catch(() => undefined);

  const { waitUntilExit } = render(<App client={client} initialStatus={initialStatus} />);
  await waitUntilExit();

  await client.shutdown().catch(() => {});
}

function formatError(exc: unknown): string {
  if (exc instanceof GatewayError) return `gateway error [${exc.code}]: ${exc.message}`;
  if (exc instanceof GatewayProtocolError) return `protocol error: ${exc.message}`;
  if (exc instanceof Error) return exc.message;
  return String(exc);
}

main().catch((exc) => {
  process.stderr.write(formatError(exc) + "\n");
  process.exit(1);
});
