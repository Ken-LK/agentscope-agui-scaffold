import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useAgentThreadRegistry } from "@/runtime/AgentRuntimeProvider";
import { PlusIcon, TrashIcon } from "lucide-react";
import type { FC } from "react";

export const ThreadList: FC = () => {
  const registry = useAgentThreadRegistry();

  return (
    <div className="aui-root aui-thread-list-root flex flex-col gap-1">
      <Button
        variant="outline"
        className="aui-thread-list-new hover:bg-muted data-active:bg-muted h-9 justify-start gap-2 rounded-lg px-3 text-sm"
        onClick={registry.createThread}
      >
        <PlusIcon className="size-4" />
        New Thread
      </Button>
      <div className="mt-1 flex flex-col gap-1">
        {registry.threads.map((thread) => (
          <ThreadListItem
            key={thread.id}
            isActive={thread.id === registry.currentThreadId}
            title={thread.title}
            canDelete={registry.threads.length > 1}
            onDelete={() => registry.deleteThread(thread.id)}
            onSwitch={() => registry.switchThread(thread.id)}
          />
        ))}
      </div>
    </div>
  );
};

const ThreadListItem: FC<{
  canDelete: boolean;
  isActive: boolean;
  onDelete: () => void;
  onSwitch: () => void;
  title: string;
}> = ({ canDelete, isActive, onDelete, onSwitch, title }) => {
  return (
    <div
      className={cn(
        "aui-thread-list-item group hover:bg-muted focus-visible:bg-muted flex h-9 items-center gap-2 rounded-lg transition-colors focus-visible:outline-none",
        isActive && "bg-muted",
      )}
      aria-current={isActive ? "true" : undefined}
    >
      <button
        type="button"
        className="aui-thread-list-item-trigger flex h-full min-w-0 flex-1 items-center px-3 text-start text-sm"
        onClick={onSwitch}
      >
        <span className="aui-thread-list-item-title min-w-0 flex-1 truncate">
          {title}
        </span>
      </button>
      {canDelete ? (
        <Button
          variant="ghost"
          size="icon"
          className="aui-thread-list-item-more text-muted-foreground hover:text-destructive me-2 size-7 p-0 opacity-0 transition-opacity group-hover:opacity-100"
          onClick={onDelete}
        >
          <TrashIcon className="size-4" />
          <span className="sr-only">Delete thread</span>
        </Button>
      ) : null}
    </div>
  );
};
