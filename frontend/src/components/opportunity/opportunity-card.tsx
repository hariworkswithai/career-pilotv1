"use client";

import Link from "next/link";
import type { OpportunityRecord } from "@/lib/opportunities/types";
import {
  employmentTypeLabel,
  formatPostedAt,
  formatSalaryMinMax,
  locationLabel,
} from "@/lib/format";
import { Card, CardContent } from "@/components/ui/card";
import { ClockIcon } from "@/components/ui/icons";
import { SaveButton } from "./save-button";

const ELIGIBILITY_STYLES: Record<string, string> = {
  eligible: "bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300",
  ambiguous: "bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300",
  not_eligible: "bg-red-50 text-red-700 dark:bg-red-900/30 dark:text-red-300",
};

export function OpportunityCard({
  opportunity,
  token,
  defaultSaved = false,
}: {
  opportunity: OpportunityRecord;
  token: string | null;
  defaultSaved?: boolean;
}) {
  const meta = [locationLabel(opportunity.location), employmentTypeLabel(opportunity.employment_type)].filter(
    Boolean
  );
  const salary = formatSalaryMinMax(
    opportunity.salary_min,
    opportunity.salary_max,
    opportunity.salary_currency,
    opportunity.salary_text
  );

  return (
    <Card hover className="hover:shadow-sm">
      <CardContent className="p-5">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <Link href={`/${opportunity.is_internship ? "internships" : "jobs"}/${opportunity.id}`}>
              <h3 className="text-base font-semibold text-slate-900 dark:text-white truncate hover:text-indigo-600 dark:hover:text-indigo-400">
                {opportunity.title}
              </h3>
            </Link>
            <p className="text-sm text-slate-500 dark:text-slate-400 mt-0.5">{opportunity.company_name}</p>
          </div>
          {token && <SaveButton opportunityId={opportunity.id} token={token} defaultSaved={defaultSaved} />}
        </div>

        <p className="text-sm text-slate-600 dark:text-slate-400 mt-3 line-clamp-2">
          {opportunity.description_text || opportunity.eligibility_reason}
        </p>

        <div className="flex flex-wrap items-center gap-2 mt-4 text-sm text-slate-600 dark:text-slate-400">
          {meta.map((m) => (
            <span
              key={m}
              className="inline-flex items-center rounded-full bg-slate-100 dark:bg-slate-700 px-2.5 py-0.5 text-xs font-medium text-slate-600 dark:text-slate-300"
            >
              {m}
            </span>
          ))}
          {salary !== "Salary not disclosed" && (
            <span className="inline-flex items-center rounded-full bg-slate-100 dark:bg-slate-700 px-2.5 py-0.5 text-xs font-medium text-slate-600 dark:text-slate-300">
              {salary}
            </span>
          )}
        </div>

        <div className="flex items-center justify-between mt-4">
          <span
            className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${ELIGIBILITY_STYLES[opportunity.india_eligible]}`}
          >
            {opportunity.india_eligible === "eligible" && "Open to India"}
            {opportunity.india_eligible === "ambiguous" && "Eligibility unclear"}
            {opportunity.india_eligible === "not_eligible" && "Not open to India"}
          </span>
          <span className="inline-flex items-center text-xs text-slate-400 dark:text-slate-500 gap-1">
            <ClockIcon className="h-3.5 w-3.5" />
            {formatPostedAt(opportunity.posted_at, true)}
          </span>
        </div>
      </CardContent>
    </Card>
  );
}