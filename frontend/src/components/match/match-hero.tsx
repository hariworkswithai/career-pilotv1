import type { MatchResult } from "@/lib/opportunities/types";
import { ProgressBar } from "@/components/ui/progress-bar";

interface MatchHeroProps {
  match: MatchResult;
  eyebrow?: string;
  actions?: React.ReactNode;
}

/**
 * Navy match-score hero (approved visual direction): big score, why-it-matches,
 * and a skill-coverage meter. Content always comes from the real match result.
 */
export function MatchHero({ match, eyebrow = "Match analysis", actions }: MatchHeroProps) {
  const matched = match.matched_skills.length;
  const gaps = match.gap_skills.length;
  const coverage = matched + gaps > 0 ? (matched / (matched + gaps)) * 100 : 0;

  return (
    <section
      aria-label="Match analysis"
      className="overflow-hidden rounded-3xl bg-indigo-950 p-6 text-white sm:p-8"
    >
      <div className="flex flex-wrap items-start justify-between gap-6">
        <div className="min-w-0 flex-1">
          <p className="text-xs font-semibold uppercase tracking-widest text-indigo-300">{eyebrow}</p>
          <p className="mt-2 text-4xl font-bold tracking-tight sm:text-5xl">{match.score}% Match</p>
          {match.explanation.slice(0, 2).map((line, i) => (
            <p key={i} className="mt-2 max-w-xl text-sm leading-relaxed text-indigo-100">
              {line}
            </p>
          ))}
          {actions && <div className="mt-5 flex flex-wrap gap-3">{actions}</div>}
        </div>
        <div className="w-full max-w-xs space-y-4">
          <ProgressBar tone="light" label="Skill coverage" value={coverage} />
          <dl className="grid grid-cols-2 gap-3 text-center">
            <div className="rounded-2xl bg-white/10 px-3 py-2.5">
              <dt className="text-[11px] font-medium uppercase tracking-wide text-indigo-200">Matched</dt>
              <dd className="text-xl font-bold">{matched}</dd>
            </div>
            <div className="rounded-2xl bg-white/10 px-3 py-2.5">
              <dt className="text-[11px] font-medium uppercase tracking-wide text-indigo-200">Gaps</dt>
              <dd className="text-xl font-bold">{gaps}</dd>
            </div>
          </dl>
        </div>
      </div>
    </section>
  );
}
