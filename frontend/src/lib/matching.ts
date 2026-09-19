export type MatchCategory = "excellent" | "strong" | "good" | "potential";

export function categoryFromScore(score: number): MatchCategory {
  if (score >= 85) return "excellent";
  if (score >= 70) return "strong";
  if (score >= 50) return "good";
  return "potential";
}

export const MATCH_CATEGORY_LABELS: Record<MatchCategory, string> = {
  excellent: "Excellent Match",
  strong: "Strong Match",
  good: "Good Match",
  potential: "Potential Match",
};