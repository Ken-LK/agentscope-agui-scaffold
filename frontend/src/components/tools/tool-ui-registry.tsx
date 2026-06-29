import type { ToolCallMessagePartComponent } from "@assistant-ui/react";

import { DefaultToolResult } from "./DefaultToolResult";

/**
 * Tool-name → renderer registry. Add an entry here to give a specific tool a
 * bespoke UI; everything else falls back to {@link DefaultToolResult}.
 *
 * This mirrors the AgentScope native web UI's `tool-renderers` pattern: known
 * tools get tailored cards, unknown tools render generically (never red-boxed).
 */
export const toolRenderers: Record<string, ToolCallMessagePartComponent> = {
  // example:
  // calculator: CalculatorToolResult,
};

export function getToolRenderer(toolName: string): ToolCallMessagePartComponent {
  return toolRenderers[toolName] ?? DefaultToolResult;
}

/** Components map for `MessagePrimitive.Parts` (`tools` slot). */
export const toolUIComponents = {
  by_name: toolRenderers,
  Fallback: DefaultToolResult,
};
