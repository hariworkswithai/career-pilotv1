import { categoryFromScore, MATCH_CATEGORY_LABELS, type MatchCategory } from "@/lib/matching";

const CATEGORY_STYLES: Record<MatchCategory, string> = {
  excellent: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-300",
  strong: "bg-indigo-100 text-indigo-800 dark:bg-indigo-900/30 dark:text-indigo-300",
  good: "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300",
  potential: "bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-300",
};

export function MatchBadge({
  score,
  size = "md",
}: {
  score: number;
  size?: "sm" | "md";
}) {
  const category = categoryFromScore(score);
  const sizeClass = size === "sm" ? "text-xs px-2 py-0.5" : "text-sm px-2.5 py-1";
  return (
    <span
      className={`inline-flex items-center rounded-full font-medium ${CATEGORY_STYLES[category]} ${sizeClass}`}
      title={`${score}% — ${MATCH_CATEGORY_LABELS[category]}`}
    >
      {score}% Match
    </span>
  );
}