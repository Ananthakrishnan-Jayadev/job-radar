import { useApp } from "../state";

const RUNNING_LABEL: Record<string, string> = {
  sizes: "Looking up company sizes",
  boards: "Finding job boards",
  "find-boards": "Finding job boards",
  levels: "Asking the AI model about job levels",
};

/** Progress of the background chore named *name*, or its last result. */
export default function TaskStatus({ name }: { name: string }) {
  const { task } = useApp();
  if (!task || task.name !== name) return null;
  if (task.running) {
    return (
      <p className="task-status" aria-live="polite">
        {RUNNING_LABEL[name] ?? "Working"}: {task.done} of {task.total || "?"}
        <progress max={task.total || 1} value={task.done} />
      </p>
    );
  }
  if (task.error) return <p className="error" role="alert">That stopped with an error: {task.error}</p>;
  return task.result ? <p className="task-status done">{task.result}</p> : null;
}
