import type { ToolCallMessagePartComponent } from "@assistant-ui/react";
import { WrenchIcon } from "lucide-react";

function stringify(value: unknown): string {
  if (value === undefined || value === null) return "";
  if (typeof value === "string") return value;
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

/**
 * Stable fallback renderer for any tool call without a dedicated UI. Keeps
 * unknown tools from producing a broken / red-boxed message part.
 */
export const DefaultToolResult: ToolCallMessagePartComponent = ({
  toolName,
  args,
  result,
}) => {
  const body = result !== undefined ? stringify(result) : stringify(args);
  return (
    <div className="my-1 rounded-md border bg-muted/40 p-3 text-sm">
      <div className="flex items-center gap-2 font-mono text-xs font-medium text-muted-foreground">
        <WrenchIcon className="size-3.5" />
        {toolName}
      </div>
      {body ? (
        <pre className="mt-2 overflow-x-auto whitespace-pre-wrap text-xs">
          {body}
        </pre>
      ) : null}
    </div>
  );
};
