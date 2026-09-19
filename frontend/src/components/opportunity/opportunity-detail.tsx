"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import type { MatchExplanation, MatchResult, OpportunityRecord } from "@/lib/opportunities/types";
import { api } from "@/lib/api";
import { getAccessToken } from "@/lib/auth";
import {
  employmentTypeLabel,
  experienceLevelLabel,
  formatPostedAt,
  formatSalaryMinMax,
  locationLabel,
} from "@/lib/format";
import { MatchBadge } from "@/components/match/match-badge";
import { MatchHero } from "@/components/match/match-hero";
import { SaveButton } from "@/components/opportunity/save-button";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  BuildingOfficeIcon,
  ClockIcon,
  ExternalLinkIcon,
} from "@/components/ui/icons";

export function OpportunityDetail({ id }: { id: string }) {
  const [token, setToken] = useState<string | null>(null);
  const [opportunity, setOpportunity] = useState<OpportunityRecord | null>(null);
  const [match, setMatch] = useState<MatchResult | null>(null);
  const [aiExplanation, setAiExplanation] = useState<MatchExplanation | null>(null);
  const [aiLoading, setAiLoading] = useState(false);
  const [saved, setSaved] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const loadedToken = useRef(false);

  useEffect(() => {
    if (!loadedToken.current) {
      loadedToken.current = true;
      getAccessToken()
        .then((t) => {
          setToken(t);
          return t;
        })
        .then((t) => {
          void api.getOpportunity(id).then(setOpportunity).catch(console.error);
          if (t) {
            void api
              .matchOpportunity(id, t)
              .then(setMatch)
              .catch(() => setMatch(null));
            void api
              .listSaved(t)
              .then((savedList) =>
                setSaved(savedList.some((o) => o.id === id))
              )
              .catch(() => setSaved(false));
          }
        })
        .finally(() => setLoading(false))
        .catch(() => {
          setError("Could not reach the CareerPilot API");
          setLoading(false);
        });
      void api
        .getOpportunity(id)
        .then(setOpportunity)
        .catch((e) => setError(e instanceof Error ? e.message : "Not found"));
    }
  }, [id]);

  if (loading && !opportunity) {
    return (
      <div className="animate-pulse space-y-4">
        <div className="h-8 w-1/2 bg-slate-200 dark:bg-slate-700 rounded" />
        <div className="h-4 w-1/3 bg-slate-200 dark:bg-slate-700 rounded" />
        <div className="h-40 w-full bg-slate-100 dark:bg-slate-800 rounded" />
      </div>
    );
  }

  if (error && !opportunity) {
    return (
      <Card>
        <CardContent className="p-8 text-center text-sm text-red-600">{error}</CardContent>
      </Card>
    );
  }

  if (!opportunity) return null;

  const salary = formatSalaryMinMax(
    opportunity.salary_min,
    opportunity.salary_max,
    opportunity.salary_currency,
    opportunity.salary_text
  );
  const link = opportunity.is_internship ? "/internships" : "/jobs";

  return (
    <div className="space-y-6">
      <Link href={link} className="text-sm text-indigo-600 dark:text-indigo-400 hover:underline">
        ← Back to {opportunity.is_internship ? "internships" : "jobs"}
      </Link>

      <Card>
        <CardContent className="p-6">
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0">
              <h1 className="text-2xl font-bold text-slate-900 dark:text-white">
                {opportunity.title}
              </h1>
              <p className="mt-1 flex items-center gap-2 text-slate-600 dark:text-slate-400">
                <BuildingOfficeIcon className="h-4 w-4" aria-hidden="true" />
                {opportunity.company_name}
              </p>
            </div>
            {token && <SaveButton opportunityId={opportunity.id} token={token} defaultSaved={saved} />}
          </div>

          <div className="mt-4 flex flex-wrap items-center gap-2">
            {match && <MatchBadge score={match.score} />}
            <span className="inline-flex items-center rounded-full bg-slate-100 dark:bg-slate-700 px-2.5 py-0.5 text-xs font-medium text-slate-600 dark:text-slate-300">
              {locationLabel(opportunity.location)}
            </span>
            <span className="inline-flex items-center rounded-full bg-slate-100 dark:bg-slate-700 px-2.5 py-0.5 text-xs font-medium text-slate-600 dark:text-slate-300">
              {employmentTypeLabel(opportunity.employment_type)}
            </span>
            {opportunity.experience_level && (
              <span className="inline-flex items-center rounded-full bg-slate-100 dark:bg-slate-700 px-2.5 py-0.5 text-xs font-medium text-slate-600 dark:text-slate-300">
                {experienceLevelLabel(opportunity.experience_level)}
              </span>
            )}
            {salary !== "Salary not disclosed" && (
              <span className="inline-flex items-center rounded-full bg-slate-100 dark:bg-slate-700 px-2.5 py-0.5 text-xs font-medium text-slate-600 dark:text-slate-300">
                {salary}
              </span>
            )}
            <span className="inline-flex items-center gap-1 text-xs text-slate-400 dark:text-slate-500">
              <ClockIcon className="h-3.5 w-3.5" />
              {formatPostedAt(opportunity.posted_at, true)}
            </span>
          </div>

          <div className="mt-4">
            <span
              className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium ${
                opportunity.india_eligible === "eligible"
                  ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300"
                  : opportunity.india_eligible === "ambiguous"
                    ? "bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300"
                    : "bg-red-50 text-red-700 dark:bg-red-900/30 dark:text-red-300"
              }`}
            >
              {opportunity.india_eligible === "eligible" && "Open to India candidates"}
              {opportunity.india_eligible === "ambiguous" && "India eligibility is unclear"}
              {opportunity.india_eligible === "not_eligible" && "Not open to India candidates"}
            </span>
            {opportunity.eligibility_reason && (
              <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">
                {opportunity.eligibility_reason}
              </p>
            )}
          </div>

          <div className="mt-6 flex flex-wrap gap-3">
            <Link href={`${link}/${opportunity.id}/apply`}>
              <Button size="lg">Apply now</Button>
            </Link>
            {opportunity.external_url && (
              <a
                href={opportunity.external_url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 rounded-lg border border-slate-300 bg-transparent px-6 py-3 text-lg font-medium text-slate-700 hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-slate-500 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-800"
              >
                View original posting <ExternalLinkIcon className="h-5 w-5" aria-hidden="true" />
              </a>
            )}
          </div>
        </CardContent>
      </Card>

      {opportunity.skills.length > 0 && (
        <Card>
          <CardContent className="p-6">
            <h2 className="text-lg font-semibold mb-3 text-slate-900 dark:text-white">Key skills</h2>
            <div className="flex flex-wrap gap-2">
              {opportunity.skills.map((skill) => (
                <span
                  key={skill}
                  className="inline-flex items-center rounded-full bg-indigo-50 dark:bg-indigo-900/30 px-3 py-1 text-sm font-medium text-indigo-700 dark:text-indigo-300"
                >
                  {skill}
                </span>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {match && (
        <>
          <MatchHero match={match} />
          <Card>
            <CardContent className="p-6">
              <h2 className="text-lg font-semibold tracking-tight mb-4 text-slate-900 dark:text-white">
                Why this matches
              </h2>
            {match.matched_skills.length > 0 && (
              <div className="mb-3">
                <p className="text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                  Matched skills
                </p>
                <div className="flex flex-wrap gap-2">
                  {match.matched_skills.map((s) => (
                    <span key={s} className="rounded-full bg-emerald-50 dark:bg-emerald-900/30 px-2.5 py-0.5 text-xs font-medium text-emerald-700 dark:text-emerald-300">
                      {s}
                    </span>
                  ))}
                </div>
              </div>
            )}
            {match.gap_skills.length > 0 && (
              <div className="mb-4">
                <p className="text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                  Potential gaps
                </p>
                <div className="flex flex-wrap gap-2">
                  {match.gap_skills.map((s) => (
                    <span key={s} className="rounded-full bg-amber-50 dark:bg-amber-900/30 px-2.5 py-0.5 text-xs font-medium text-amber-700 dark:text-amber-300">
                      {s}
                    </span>
                  ))}
                </div>
              </div>
            )}
            <ul className="mt-2 space-y-1.5 text-sm leading-relaxed text-slate-600 dark:text-slate-400">
              {match.explanation.map((line, i) => (
                <li key={i} className="flex gap-2">
                  <span className="text-indigo-500" aria-hidden="true">•</span>
                  {line}
                </li>
              ))}
            </ul>
            {token && (
              <div className="mt-4 border-t border-slate-100 pt-4 dark:border-slate-800">
                {!aiExplanation && !aiLoading && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      if (!token) return;
                      setAiLoading(true);
                      api
                        .explainMatch(id, token)
                        .then(setAiExplanation)
                        .catch(() => setAiExplanation(null))
                        .finally(() => setAiLoading(false));
                    }}
                  >
                    Explain this match with AI
                  </Button>
                )}
                {aiLoading && (
                  <p className="text-sm text-slate-500" aria-busy="true">
                    Generating explanation…
                  </p>
                )}
                {aiExplanation?.ai_summary && (
                  <div>
                    <p className="text-sm font-medium text-slate-700 dark:text-slate-300">
                      AI explanation
                      {aiExplanation.cached && (
                        <span className="ml-2 text-xs font-normal text-slate-400">(cached)</span>
                      )}
                    </p>
                    <p className="mt-1 whitespace-pre-line text-sm leading-relaxed text-slate-600 dark:text-slate-400">
                      {aiExplanation.ai_summary}
                    </p>
                  </div>
                )}
              </div>
            )}
          </CardContent>
        </Card>
        </>
      )}

      {opportunity.description_html && (
        <Card>
          <CardContent className="p-6 prose prose-slate dark:prose-invert max-w-none">
            <h2 className="text-lg font-semibold mb-3 text-slate-900 dark:text-white">About the role</h2>
            <div
              dangerouslySetInnerHTML={{ __html: opportunity.description_html }}
            />
          </CardContent>
        </Card>
      )}
    </div>
  );
}