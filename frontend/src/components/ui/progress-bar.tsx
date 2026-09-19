interface ProgressBarProps {
  value: number;
  max?: number;
  label?: string;
  /** "light" renders for use on navy surfaces. */
  tone?: "brand" | "light";
  className?: string;
}

/**
 * Accessible progress bar (skill-match meters, profile completeness).
 */
export function ProgressBar({ value, max = 100, label, tone = "brand", className = "" }: ProgressBarProps) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100));
  const track = tone === "light" ? "bg-white/20" : "bg-slate-200 dark:bg-slate-700";
  const fill = tone === "light" ? "bg-white" : "bg-indigo-600";
  return (
    <div className={className}>
      {label && (
        <div className="mb-1 flex items-center justify-between text-xs">
          <span className={tone === "light" ? "text-indigo-100" : "text-slate-600 dark:text-slate-400"}>
            {label}
          </span>
          <span className={tone === "light" ? "font-semibold text-white" : "font-medium text-slate-700 dark:text-slate-300"}>
            {Math.round(pct)}%
          </span>
        </div>
      )}
      <div
        className={`h-2 overflow-hidden rounded-full ${track}`}
        role="progressbar"
        aria-valuenow={Math.round(pct)}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={label ?? "Progress"}
      >
        <div className={`h-full rounded-full transition-[width] ${fill}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
