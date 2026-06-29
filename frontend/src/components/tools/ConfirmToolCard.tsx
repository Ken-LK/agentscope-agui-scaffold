import { useMemo, useState } from "react";
import { ShieldAlertIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/**
 * A write-tool call awaiting confirmation, as carried by the official
 * AgentScope `CUSTOM("require_user_confirm")` AG-UI event value.
 */
export type ConfirmToolCall = {
  id: string;
  name: string;
  input?: string;
};

export type ConfirmDecision = {
  toolCallId: string;
  confirmed: boolean;
};

export type ConfirmToolCardProps = {
  replyId: string;
  toolCalls: ConfirmToolCall[];
  /** Resolve every awaiting tool call with one approve/reject choice. */
  onResolve: (replyId: string, decisions: ConfirmDecision[]) => void;
  disabled?: boolean;
  className?: string;
};

function formatInput(input?: string): string {
  if (!input) return "";
  try {
    return JSON.stringify(JSON.parse(input), null, 2);
  } catch {
    return input;
  }
}

export function ConfirmToolCard({
  replyId,
  toolCalls,
  onResolve,
  disabled = false,
  className,
}: ConfirmToolCardProps) {
  const [resolved, setResolved] = useState<boolean | null>(null);

  const decisions = useMemo(
    () => (confirmed: boolean): ConfirmDecision[] =>
      toolCalls.map((tc) => ({ toolCallId: tc.id, confirmed })),
    [toolCalls],
  );

  const resolve = (confirmed: boolean) => {
    if (disabled || resolved !== null) return;
    setResolved(confirmed);
    onResolve(replyId, decisions(confirmed));
  };

  return (
    <div
      className={cn(
        "flex flex-col gap-3 rounded-lg border border-amber-300 bg-amber-50 p-4 text-sm dark:border-amber-700 dark:bg-amber-950/40",
        className,
      )}
    >
      <div className="flex items-center gap-2 font-medium text-amber-900 dark:text-amber-200">
        <ShieldAlertIcon className="size-4" />
        需要确认写操作
      </div>

      <ul className="flex flex-col gap-2">
        {toolCalls.map((tc) => (
          <li key={tc.id} className="rounded-md bg-white/70 p-2 dark:bg-black/20">
            <div className="font-mono text-xs font-semibold">{tc.name}</div>
            {tc.input ? (
              <pre className="mt-1 overflow-x-auto whitespace-pre-wrap text-xs text-muted-foreground">
                {formatInput(tc.input)}
              </pre>
            ) : null}
          </li>
        ))}
      </ul>

      {resolved === null ? (
        <div className="flex gap-2">
          <Button
            size="sm"
            onClick={() => resolve(true)}
            disabled={disabled}
          >
            批准
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={() => resolve(false)}
            disabled={disabled}
          >
            拒绝
          </Button>
        </div>
      ) : (
        <div className="text-xs text-muted-foreground">
          {resolved ? "已批准" : "已拒绝"}
        </div>
      )}
    </div>
  );
}
